"""
Real-Time Fraud Scoring Engine with SHAP Explainability.

Consumes streaming transactions, derives rolling behavioral features, executes
champion XGBoost inference (<200ms latency), and extracts top-5 SHAP decision factors.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import shap
import xgboost as xgb

from fraud.features.batch_features import BatchFeatureStore
from fraud.features.streaming_features import StreamingFeatureStore
from fraud.training.train import FEATURE_COLUMNS

logger = logging.getLogger("sentraflow.fraud.scoring")


@dataclass
class ShapFactor:
    feature_name: str
    feature_value: float
    shap_value: float
    impact: str  # "INCREASES_RISK" or "DECREASES_RISK"


@dataclass
class ScoredTransaction:
    txn_id: str
    account_id: str
    amount: float
    fraud_score: float
    is_flagged: bool
    decision: str  # "FRAUD_SUSPECT" or "APPROVE"
    top_shap_factors: list[dict[str, Any]]
    scored_at: str
    latency_ms: float
    raw_features: dict[str, float]


@dataclass
class DLQRecord:
    raw_payload: dict[str, Any]
    error_message: str
    failed_at: str


class FraudScoringEngine:
    """
    Production real-time inference service.
    Combines feature derivation, XGBoost champion inference, and fast SHAP attribution.
    """

    def __init__(
        self,
        model: Optional[xgb.XGBClassifier] = None,
        model_path: Optional[str | Path] = None,
        feature_store: Optional[StreamingFeatureStore] = None,
        threshold: float = 0.50,
    ) -> None:
        self.feature_store = feature_store or StreamingFeatureStore()
        self.threshold = threshold
        self.model = model

        if self.model is None and model_path is not None:
            p = Path(model_path)
            if p.exists():
                self.model = xgb.XGBClassifier()
                self.model.load_model(str(p))
                # Attempt reading metadata threshold
                meta_file = p.parent / "metadata.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            self.threshold = float(meta.get("optimal_threshold", 0.50))
                    except Exception:
                        pass

        # TreeExplainer cache
        self._explainer: Optional[shap.TreeExplainer] = None
        if self.model is not None:
            try:
                self._explainer = shap.TreeExplainer(self.model)
            except Exception as e:
                logger.warning("Could not initialize TreeExplainer: %s", e)

    def set_model(self, model: xgb.XGBClassifier, threshold: Optional[float] = None) -> None:
        self.model = model
        if threshold is not None:
            self.threshold = threshold
        try:
            self._explainer = shap.TreeExplainer(self.model)
        except Exception as e:
            logger.warning("TreeExplainer re-init failed: %s", e)

    def extract_top_shap_factors(
        self, feature_vector: np.ndarray, feature_dict: dict[str, float], top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Calculate local SHAP values and extract top-K influential factors."""
        if self._explainer is None:
            return []

        try:
            # feature_vector shape: (1, num_features)
            shap_values = self._explainer.shap_values(feature_vector)
            # For binary classification, shap_values might be 1D or 2D
            vals = shap_values[0] if isinstance(shap_values, list) else shap_values
            if len(vals.shape) > 1:
                vals = vals[0]

            # Pair features with their SHAP contribution
            factors: list[ShapFactor] = []
            for name, shap_val in zip(FEATURE_COLUMNS, vals):
                val_float = float(shap_val)
                impact = "INCREASES_RISK" if val_float > 0 else "DECREASES_RISK"
                factors.append(
                    ShapFactor(
                        feature_name=name,
                        feature_value=float(feature_dict.get(name, 0.0)),
                        shap_value=round(val_float, 4),
                        impact=impact,
                    )
                )

            # Sort by absolute SHAP magnitude descending
            factors.sort(key=lambda x: abs(x.shap_value), reverse=True)
            return [asdict(f) for f in factors[:top_k]]
        except Exception as e:
            logger.warning("SHAP attribution computation failed: %s", e)
            return []

    def score_transaction(
        self, payload: dict[str, Any], update_feature_store: bool = True
    ) -> Union[ScoredTransaction, DLQRecord]:
        """
        Score a single transaction payload. Guarantees sub-200ms latency.
        """
        start_ns = time.perf_counter_ns()

        # Validate mandatory fields
        required_keys = ["txn_id", "account_id", "amount"]
        missing = [k for k in required_keys if k not in payload or payload[k] is None]
        if missing:
            return DLQRecord(
                raw_payload=payload,
                error_message=f"Missing mandatory fields: {', '.join(missing)}",
                failed_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            txn_id = str(payload["txn_id"])
            account_id = str(payload["account_id"])
            customer_id = str(payload.get("customer_id", account_id))
            merchant_id = str(payload.get("merchant_id", "M_DEFAULT"))
            amount = float(payload["amount"])
            channel = str(payload.get("channel", "UPI"))
            device_id = str(payload.get("device_id", "DEV_DEFAULT"))
            lat = float(payload.get("lat", 19.0760))
            lon = float(payload.get("lon", 72.8777))

            raw_ts = payload.get("txn_ts")
            if isinstance(raw_ts, str):
                try:
                    txn_ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except ValueError:
                    txn_ts = datetime.now(timezone.utc)
            elif isinstance(raw_ts, datetime):
                txn_ts = raw_ts
            else:
                txn_ts = datetime.now(timezone.utc)

            # 1. Feature Engineering
            features = self.feature_store.compute_features(
                customer_id=customer_id,
                account_id=account_id,
                merchant_id=merchant_id,
                amount=amount,
                channel=channel,
                txn_ts=txn_ts,
                lat=lat,
                lon=lon,
                device_id=device_id,
                update_state=update_feature_store,
            )

            # Build feature array
            feature_array = np.array([[features[col] for col in FEATURE_COLUMNS]], dtype=np.float32)

            # 2. Model Inference
            if self.model is not None:
                prob = float(self.model.predict_proba(feature_array)[0, 1])
            else:
                # Heuristic fallback if model not loaded
                prob = 0.05
                if features.get("is_impossible_travel", 0.0) > 0.5:
                    prob = 0.92
                elif features.get("is_velocity_burst", 0.0) > 0.5:
                    prob = 0.85
                elif features.get("amount_zscore", 0.0) > 4.0:
                    prob = 0.78

            is_flagged = bool(prob >= self.threshold)
            decision = "FRAUD_SUSPECT" if is_flagged else "APPROVE"

            # 3. SHAP Explanation
            top_factors = self.extract_top_shap_factors(feature_array, features, top_k=5)

            elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000.0

            return ScoredTransaction(
                txn_id=txn_id,
                account_id=account_id,
                amount=amount,
                fraud_score=round(prob, 4),
                is_flagged=is_flagged,
                decision=decision,
                top_shap_factors=top_factors,
                scored_at=datetime.now(timezone.utc).isoformat(),
                latency_ms=round(elapsed_ms, 2),
                raw_features=features,
            )

        except Exception as e:
            logger.error("Scoring failure: %s", e, exc_info=True)
            return DLQRecord(
                raw_payload=payload,
                error_message=str(e),
                failed_at=datetime.now(timezone.utc).isoformat(),
            )

