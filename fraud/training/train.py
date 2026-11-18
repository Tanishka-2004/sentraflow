"""
Model Training Pipeline for SentraFlow Fraud Engine.

Trains an XGBoost classifier with cost-matrix threshold tuning, PR-AUC optimization,
and MLflow experiment tracking.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
)
import xgboost as xgb

logger = logging.getLogger("sentraflow.fraud.training")

FEATURE_COLUMNS: list[str] = [
    "amount",
    "avg_ticket_size",
    "amount_zscore",
    "txn_count_1m",
    "txn_count_5m",
    "txn_count_60m",
    "txn_amount_sum_10m",
    "dist_from_last_txn_km",
    "implied_speed_kmh",
    "is_impossible_travel",
    "is_new_device",
    "is_high_value_night",
    "is_velocity_burst",
    "merchant_risk_score",
    "merchant_chargeback_rate",
    "channel_code",
    "hour_of_day",
]


@dataclass
class TrainingMetrics:
    pr_auc: float
    roc_auc: float
    f1_optimal: float
    optimal_threshold: float
    brier_score: float
    precision_at_optimal: float
    recall_at_optimal: float
    recall_at_95_precision: float
    confusion_matrix: list[list[int]]
    total_cost: float


def compute_cost_matrix_threshold(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    amounts: np.ndarray,
    fp_friction_cost: float = 50.0,
    steps: int = 100,
) -> tuple[float, float]:
    """
    Tune classification threshold to minimize financial cost:
    Cost = (FP count * fp_friction_cost) + sum(FN amounts)
    """
    best_threshold = 0.5
    min_cost = float("inf")

    thresholds = np.linspace(0.05, 0.95, steps)
    for t in thresholds:
        preds = (y_prob >= t).astype(int)
        fps = (preds == 1) & (y_true == 0)
        fns = (preds == 0) & (y_true == 1)

        fp_cost = float(np.sum(fps)) * fp_friction_cost
        fn_cost = float(np.sum(amounts[fns]))
        total_cost = fp_cost + fn_cost

        if total_cost < min_cost:
            min_cost = total_cost
            best_threshold = float(t)

    return best_threshold, min_cost


def evaluate_model(
    model: xgb.XGBClassifier,
    X_val: np.ndarray,
    y_val: np.ndarray,
    amounts_val: np.ndarray,
    fp_friction_cost: float = 50.0,
) -> TrainingMetrics:
    """Evaluate classifier performance and compute production metrics."""
    y_prob = model.predict_proba(X_val)[:, 1]

    pr_auc = float(average_precision_score(y_val, y_prob))
    roc_auc = float(roc_auc_score(y_val, y_prob)) if len(np.unique(y_val)) > 1 else 0.5
    brier = float(brier_score_loss(y_val, y_prob))

    # Cost-matrix optimal threshold
    best_thresh, min_cost = compute_cost_matrix_threshold(
        y_val, y_prob, amounts_val, fp_friction_cost=fp_friction_cost
    )

    y_pred_optimal = (y_prob >= best_thresh).astype(int)
    f1_opt = float(f1_score(y_val, y_pred_optimal, zero_division=0))

    cm = confusion_matrix(y_val, y_pred_optimal).tolist()
    tn, fp, fn, tp = confusion_matrix(y_val, y_pred_optimal).ravel()
    prec = tp / max(1, (tp + fp))
    rec = tp / max(1, (tp + fn))

    # Recall at ~95% precision
    precisions, recalls, _ = precision_recall_curve(y_val, y_prob)
    high_prec_mask = precisions >= 0.90
    rec_at_95 = float(np.max(recalls[high_prec_mask])) if np.any(high_prec_mask) else 0.0

    return TrainingMetrics(
        pr_auc=pr_auc,
        roc_auc=roc_auc,
        f1_optimal=f1_opt,
        optimal_threshold=best_thresh,
        brier_score=brier,
        precision_at_optimal=float(prec),
        recall_at_optimal=float(rec),
        recall_at_95_precision=rec_at_95,
        confusion_matrix=cm,
        total_cost=min_cost,
    )


def train_fraud_model(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    output_dir: str | Path = "fraud/models",
    experiment_name: str = "sentraflow_fraud_detection",
    scale_pos_weight: Optional[float] = None,
    n_estimators: int = 40,
) -> tuple[xgb.XGBClassifier, TrainingMetrics]:
    """
    Train XGBoost model, evaluate metrics, and save production artifacts.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    X_train = train_df[FEATURE_COLUMNS].values
    y_train = train_df["is_fraud"].values.astype(int)

    X_val = val_df[FEATURE_COLUMNS].values
    y_val = val_df["is_fraud"].values.astype(int)
    amounts_val = val_df["amount"].values.astype(float)

    # Class imbalance weighting
    pos_count = int(np.sum(y_train == 1))
    neg_count = int(np.sum(y_train == 0))
    if scale_pos_weight is None:
        scale_pos_weight = float(neg_count / max(1, pos_count))

    model = xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="aucpr",
        random_state=42,
    )

    model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )

    metrics = evaluate_model(model, X_val, y_val, amounts_val)

    # Persist champion model artifact and metadata
    model_file = out_path / "champion_model.json"
    model.save_model(str(model_file))

    metadata = {
        "model_type": "xgboost.XGBClassifier",
        "feature_names": FEATURE_COLUMNS,
        "optimal_threshold": metrics.optimal_threshold,
        "pr_auc": metrics.pr_auc,
        "roc_auc": metrics.roc_auc,
        "f1_optimal": metrics.f1_optimal,
        "brier_score": metrics.brier_score,
        "confusion_matrix": metrics.confusion_matrix,
        "total_cost": metrics.total_cost,
    }
    with open(out_path / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # Attempt MLflow logging if available to local directory
    try:
        import mlflow
        import mlflow.xgboost

        mlruns_dir = out_path / "mlruns"
        mlruns_dir.mkdir(parents=True, exist_ok=True)
        mlflow.set_tracking_uri(f"file:///{mlruns_dir.resolve().as_posix()}")
        mlflow.set_experiment(experiment_name)
        with mlflow.start_run(run_name="champion_xgboost_run"):
            mlflow.log_params(
                {
                    "n_estimators": n_estimators,
                    "max_depth": 4,
                    "learning_rate": 0.1,
                    "scale_pos_weight": scale_pos_weight,
                    "features_count": len(FEATURE_COLUMNS),
                }
            )
            mlflow.log_metrics(
                {
                    "pr_auc": metrics.pr_auc,
                    "roc_auc": metrics.roc_auc,
                    "f1_optimal": metrics.f1_optimal,
                    "optimal_threshold": metrics.optimal_threshold,
                    "brier_score": metrics.brier_score,
                    "recall_at_95_precision": metrics.recall_at_95_precision,
                }
            )
            mlflow.xgboost.log_model(model, artifact_path="model")
            logger.info("Successfully tracked experiment with MLflow.")
    except Exception as e:
        logger.debug("MLflow tracking skipped: %s", e)

    return model, metrics
