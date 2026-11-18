"""
Comprehensive Unit Tests for SentraFlow Real-Time Fraud Engine.

Verifies feature derivation, model training, SHAP attribution,
real-time scoring latency (<200ms), and DLQ error routing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import time
from typing import Tuple
import numpy as np
import pandas as pd
import pytest
import xgboost as xgb

from fraud.explain.explainer import FraudExplainer
from fraud.features.batch_features import BatchFeatureStore
from fraud.features.streaming_features import StreamingFeatureStore, haversine_distance_km
from fraud.scoring_service.scorer import DLQRecord, FraudScoringEngine, ScoredTransaction
from fraud.training.train import FEATURE_COLUMNS, TrainingMetrics, train_fraud_model


def _generate_synthetic_training_data(n_samples: int = 350) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.RandomState(42)

    data = []
    for i in range(n_samples):
        is_fraud = 1 if rng.rand() < 0.08 else 0
        if is_fraud:
            amt = float(rng.uniform(15000, 90000))
            zscore = float(rng.uniform(3.5, 12.0))
            count_5m = float(rng.choice([3, 4, 6]))
            speed = float(rng.choice([0.0, 950.0, 1200.0]))
            impossible = 1.0 if speed > 800.0 else 0.0
            new_dev = float(rng.choice([0.0, 1.0, 1.0]))
            merch_risk = float(rng.choice([0.65, 0.95]))
            is_night = float(rng.choice([0.0, 1.0]))
        else:
            amt = float(rng.uniform(100, 3000))
            zscore = float(rng.uniform(-1.0, 1.5))
            count_5m = float(rng.choice([0, 1]))
            speed = float(rng.uniform(0.0, 60.0))
            impossible = 0.0
            new_dev = 0.0
            merch_risk = 0.05
            is_night = 0.0

        row = {
            "amount": amt,
            "avg_ticket_size": 1500.0,
            "amount_zscore": zscore,
            "txn_count_1m": float(count_5m),
            "txn_count_5m": float(count_5m),
            "txn_count_60m": float(count_5m + 1),
            "txn_amount_sum_10m": amt * 0.8,
            "dist_from_last_txn_km": 500.0 if impossible else 5.0,
            "implied_speed_kmh": speed,
            "is_impossible_travel": impossible,
            "is_new_device": new_dev,
            "is_high_value_night": is_night,
            "is_velocity_burst": 1.0 if count_5m >= 3 else 0.0,
            "merchant_risk_score": merch_risk,
            "merchant_chargeback_rate": 0.05 if is_fraud else 0.002,
            "channel_code": 2.0,
            "hour_of_day": 2.0 if is_night else 14.0,
            "is_fraud": is_fraud,
        }
        data.append(row)

    df = pd.DataFrame(data)
    train_df = df.iloc[: int(0.75 * n_samples)].copy()
    val_df = df.iloc[int(0.75 * n_samples) :].copy()
    return train_df, val_df


@pytest.fixture(scope="module")
def trained_artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[xgb.XGBClassifier, TrainingMetrics, pd.DataFrame]:
    tmp_dir = tmp_path_factory.mktemp("fraud_models")
    train_df, val_df = _generate_synthetic_training_data(n_samples=350)
    model, metrics = train_fraud_model(
        train_df=train_df,
        val_df=val_df,
        output_dir=tmp_dir,
        experiment_name="test_experiment",
        n_estimators=30,
    )
    return model, metrics, val_df


def test_haversine_and_impossible_travel() -> None:
    # Mumbai (19.0760, 72.8777) to Delhi (28.6139, 77.2090) ~ 1150 km
    dist = haversine_distance_km(19.0760, 72.8777, 28.6139, 77.2090)
    assert 1100.0 < dist < 1200.0

    store = StreamingFeatureStore()
    now = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)

    # First txn in Mumbai
    f1 = store.compute_features(
        customer_id="C_TRAVEL_1",
        account_id="A_TRAVEL_1",
        merchant_id="M_MUMBAI",
        amount=500.0,
        channel="CARD",
        txn_ts=now,
        lat=19.0760,
        lon=72.8777,
        device_id="DEV_MUMBAI",
    )
    assert f1["is_impossible_travel"] == 0.0

    # Second txn 10 minutes later in Delhi (~1150 km away -> implied speed ~ 6900 km/h)
    f2 = store.compute_features(
        customer_id="C_TRAVEL_1",
        account_id="A_TRAVEL_1",
        merchant_id="M_DELHI",
        amount=45000.0,
        channel="CARD",
        txn_ts=now + timedelta(minutes=10),
        lat=28.6139,
        lon=77.2090,
        device_id="DEV_MUMBAI",
    )
    assert f2["dist_from_last_txn_km"] > 1000.0
    assert f2["implied_speed_kmh"] > 1000.0
    assert f2["is_impossible_travel"] == 1.0


def test_streaming_rolling_window_features() -> None:
    batch_store = BatchFeatureStore()
    batch_store.register_customer(
        customer_id="C_ROLLING_1",
        avg_ticket_size=1000.0,
        std_ticket_size=200.0,
        initial_devices=["PHONE_PRIMARY"],
    )
    store = StreamingFeatureStore(batch_store=batch_store)
    base_ts = datetime(2026, 8, 1, 14, 0, 0, tzinfo=timezone.utc)

    # 1. Normal txn
    f1 = store.compute_features(
        customer_id="C_ROLLING_1",
        account_id="ACC_1",
        merchant_id="M1",
        amount=1200.0,
        channel="UPI",
        txn_ts=base_ts,
        lat=19.076,
        lon=72.877,
        device_id="PHONE_PRIMARY",
    )
    assert f1["txn_count_1m"] == 0.0
    assert f1["is_new_device"] == 0.0
    assert abs(f1["amount_zscore"] - 1.0) < 1e-4

    # 2. Burst txn 30 seconds later from a NEW device
    f2 = store.compute_features(
        customer_id="C_ROLLING_1",
        account_id="ACC_1",
        merchant_id="M1",
        amount=5000.0,
        channel="UPI",
        txn_ts=base_ts + timedelta(seconds=30),
        lat=19.076,
        lon=72.877,
        device_id="UNKNOWN_LAPTOP",
    )
    assert f2["txn_count_1m"] == 1.0
    assert f2["is_new_device"] == 1.0
    assert f2["txn_amount_sum_10m"] == 1200.0
    assert f2["amount_zscore"] == 20.0


def test_model_training_and_cost_optimization(trained_artifacts: tuple[xgb.XGBClassifier, TrainingMetrics, pd.DataFrame]) -> None:
    _, metrics, _ = trained_artifacts
    assert metrics.pr_auc > 0.40
    assert metrics.roc_auc > 0.70
    assert 0.05 <= metrics.optimal_threshold <= 0.95
    assert metrics.f1_optimal > 0.0


def test_scoring_engine_and_shap_factors(trained_artifacts: tuple[xgb.XGBClassifier, TrainingMetrics, pd.DataFrame]) -> None:
    model, metrics, _ = trained_artifacts
    engine = FraudScoringEngine(model=model, threshold=metrics.optimal_threshold)

    # 1. Test normal benign transaction
    benign_payload = {
        "txn_id": "TXN_BENIGN_001",
        "account_id": "ACC_B_1",
        "customer_id": "CUST_B_1",
        "amount": 450.0,
        "channel": "UPI",
        "lat": 19.0760,
        "lon": 72.8777,
        "device_id": "KNOWN_DEV_1",
    }
    scored = engine.score_transaction(benign_payload)
    assert isinstance(scored, ScoredTransaction)
    assert scored.decision == "APPROVE"
    assert scored.fraud_score < metrics.optimal_threshold
    assert len(scored.top_shap_factors) <= 5

    # 2. Test severe fraud burst (impossible travel + high amount z-score)
    engine.score_transaction(
        {
            "txn_id": "TXN_PRIME",
            "account_id": "ACC_SUSPECT",
            "customer_id": "CUST_SUSPECT",
            "amount": 200.0,
            "lat": 19.0760,
            "lon": 72.8777,
            "device_id": "DEV_A",
        }
    )

    fraud_payload = {
        "txn_id": "TXN_FRAUD_BURST",
        "account_id": "ACC_SUSPECT",
        "customer_id": "CUST_SUSPECT",
        "amount": 85000.0,
        "channel": "CARD",
        "lat": 28.6139,
        "lon": 77.2090,
        "device_id": "DEV_UNKNOWN",
    }
    fraud_scored = engine.score_transaction(fraud_payload)
    assert isinstance(fraud_scored, ScoredTransaction)
    assert fraud_scored.decision == "FRAUD_SUSPECT"
    assert fraud_scored.is_flagged is True
    assert fraud_scored.fraud_score >= metrics.optimal_threshold

    factor_names = [f["feature_name"] for f in fraud_scored.top_shap_factors]
    assert any(
        f in factor_names
        for f in ["is_impossible_travel", "amount", "amount_zscore", "is_new_device"]
    )


def test_dlq_routing_on_malformed_event() -> None:
    engine = FraudScoringEngine()
    bad_payload = {"txn_id": "CORRUPT_TXN_001"}
    result = engine.score_transaction(bad_payload)

    assert isinstance(result, DLQRecord)
    assert "Missing mandatory fields" in result.error_message
    assert result.raw_payload == bad_payload


def test_scoring_latency_p95_under_200ms(trained_artifacts: tuple[xgb.XGBClassifier, TrainingMetrics, pd.DataFrame]) -> None:
    model, metrics, _ = trained_artifacts
    engine = FraudScoringEngine(model=model, threshold=metrics.optimal_threshold)

    latencies_ms = []
    # Warm up run
    engine.score_transaction(
        {"txn_id": "WARMUP", "account_id": "A1", "amount": 100.0, "device_id": "D1"}
    )

    # Benchmark 30 sequential transactions
    for i in range(30):
        payload = {
            "txn_id": f"TXN_BENCH_{i}",
            "account_id": f"ACC_{i % 5}",
            "customer_id": f"CUST_{i % 5}",
            "amount": float(500 + (i * 10)),
            "channel": "UPI",
            "lat": 19.0760,
            "lon": 72.8777,
            "device_id": f"DEV_{i % 3}",
        }
        res = engine.score_transaction(payload)
        assert isinstance(res, ScoredTransaction)
        latencies_ms.append(res.latency_ms)

    p95_latency = np.percentile(latencies_ms, 95)
    print(f"\n[LATENCY BENCHMARK] p50={np.median(latencies_ms):.2f}ms, p95={p95_latency:.2f}ms")
    assert p95_latency < 200.0


def test_waterfall_explanation_structure(trained_artifacts: tuple[xgb.XGBClassifier, TrainingMetrics, pd.DataFrame]) -> None:
    model, _, val_df = trained_artifacts
    explainer = FraudExplainer(model)

    features = {col: 1.0 for col in FEATURE_COLUMNS}
    features["amount"] = 55000.0
    features["is_impossible_travel"] = 1.0

    wf = explainer.generate_waterfall_explanation("TXN_EXPLAIN_01", features)
    assert wf.txn_id == "TXN_EXPLAIN_01"
    assert len(wf.steps) == len(FEATURE_COLUMNS)
    assert 0.0 <= wf.final_score <= 1.0

    X_sample = val_df[FEATURE_COLUMNS].values[:20]
    summary = explainer.export_global_summary_data(X_sample)
    assert summary["num_samples"] == 20
    assert len(summary["feature_importances"]) == len(FEATURE_COLUMNS)
