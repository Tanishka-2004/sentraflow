"""
Explainability Module for SentraFlow Fraud Engine.

Generates structured waterfall breakdowns for single transactions and global
feature importance summaries for model audits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import shap
import xgboost as xgb

from fraud.training.train import FEATURE_COLUMNS

logger = logging.getLogger("sentraflow.fraud.explain")


@dataclass
class WaterfallStep:
    feature_name: str
    feature_value: float
    contribution: float
    cumulative_score: float
    impact: str  # "INCREASES_RISK" or "DECREASES_RISK"


@dataclass
class TransactionWaterfallExplanation:
    txn_id: str
    base_value: float
    final_score: float
    steps: list[WaterfallStep]


class FraudExplainer:
    """Manages local transaction waterfall explanations and global model interpretability."""

    def __init__(self, model: xgb.XGBClassifier) -> None:
        self.model = model
        self.explainer = shap.TreeExplainer(model)
        # Expected base value (prior probability or log-odds)
        base = self.explainer.expected_value
        if isinstance(base, (list, np.ndarray)):
            self.base_value = float(base[-1]) if len(base) > 1 else float(base[0])
        else:
            self.base_value = float(base)

    def generate_waterfall_explanation(
        self, txn_id: str, feature_dict: dict[str, float]
    ) -> TransactionWaterfallExplanation:
        """
        Produce a step-by-step waterfall attribution suitable for frontend Recharts rendering.
        """
        feature_vals = [float(feature_dict.get(col, 0.0)) for col in FEATURE_COLUMNS]
        X = np.array([feature_vals], dtype=np.float32)

        shap_vals = self.explainer.shap_values(X)
        vals = shap_vals[0] if isinstance(shap_vals, list) else shap_vals
        if len(vals.shape) > 1:
            vals = vals[0]

        steps: list[WaterfallStep] = []
        current_cumulative = self.base_value

        # Sort features by absolute contribution magnitude
        indexed_contributions = sorted(
            list(enumerate(vals)), key=lambda pair: abs(float(pair[1])), reverse=True
        )

        for idx, contrib in indexed_contributions:
            contrib_float = float(contrib)
            current_cumulative += contrib_float
            col_name = FEATURE_COLUMNS[idx]
            steps.append(
                WaterfallStep(
                    feature_name=col_name,
                    feature_value=round(feature_vals[idx], 4),
                    contribution=round(contrib_float, 4),
                    cumulative_score=round(current_cumulative, 4),
                    impact="INCREASES_RISK" if contrib_float > 0 else "DECREASES_RISK",
                )
            )

        prob = float(self.model.predict_proba(X)[0, 1])

        return TransactionWaterfallExplanation(
            txn_id=txn_id,
            base_value=round(self.base_value, 4),
            final_score=round(prob, 4),
            steps=steps,
        )

    def export_global_summary_data(self, X_sample: np.ndarray) -> dict[str, Any]:
        """Compute global mean absolute SHAP importances across sample population."""
        shap_vals = self.explainer.shap_values(X_sample)
        vals = shap_vals[0] if isinstance(shap_vals, list) else shap_vals
        if len(vals.shape) == 3:
            vals = vals[1]

        mean_abs_shap = np.mean(np.abs(vals), axis=0)
        importances = [
            {"feature": col, "mean_abs_shap": round(float(imp), 4)}
            for col, imp in zip(FEATURE_COLUMNS, mean_abs_shap)
        ]
        importances.sort(key=lambda x: x["mean_abs_shap"], reverse=True)
        return {
            "num_samples": int(X_sample.shape[0]),
            "feature_importances": importances,
        }

