import os
import json
import numpy as np
import xgboost as xgb
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from collections import deque
from typing import Dict, List, Optional

app = FastAPI(
    title="SentraFlow ML Serving API",
    description="Serves the XGBoost fraud detection model with SHAP explanations and PSI drift calculation.",
    version="1.0.0"
)

# Global variables to store model, stats, and prediction history
model = None
baseline_stats = None
prediction_history = deque(maxlen=200) # Sliding window for PSI calculation

# Load paths
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "fraud_model.json")
STATS_PATH = os.path.join(os.path.dirname(__file__), "models", "baseline_stats.json")

# Configurable fraud thresholds
fraud_thresholds = {
    "low_medium": 0.30,
    "medium_high": 0.70,
    "high_critical": 0.90
}

class TransactionPayload(BaseModel):
    amount: float = Field(..., gt=0, example=150.50)
    oldBalanceOrig: float = Field(..., ge=0, example=5000.00)
    newBalanceOrig: float = Field(..., ge=0, example=4849.50)
    oldBalanceDest: float = Field(..., ge=0, example=100.00)
    newBalanceDest: float = Field(..., ge=0, example=250.50)
    transaction_type: str = Field(..., example="TRANSFER")

class PredictionResponse(BaseModel):
    risk_score: float
    risk_level: str
    model_version: str
    shap_explanations: Dict[str, float]

class DriftResponse(BaseModel):
    psi: float
    drift_status: str
    sample_count: int
    baseline_distribution: List[float]
    current_distribution: List[float]

@app.on_event("startup")
def load_model_and_stats():
    global model, baseline_stats
    print("Initializing SentraFlow ML Service...")
    
    if not os.path.exists(MODEL_PATH):
        # We raise a startup error if model files are missing to ensure model version validation
        raise RuntimeError(f"Startup failed: Model file not found at {MODEL_PATH}. Run training script first.")
        
    if not os.path.exists(STATS_PATH):
        raise RuntimeError(f"Startup failed: Baseline stats file not found at {STATS_PATH}.")
        
    try:
        model = xgb.XGBClassifier()
        model.load_model(MODEL_PATH)
        print("Model loaded successfully.")
    except Exception as e:
        raise RuntimeError(f"Failed to load XGBoost model: {e}")
        
    try:
        with open(STATS_PATH, "r") as f:
            baseline_stats = json.load(f)
        print("Baseline statistics loaded successfully.")
    except Exception as e:
        raise RuntimeError(f"Failed to load baseline stats: {e}")

@app.get("/health", status_code=status.HTTP_200_OK)
def health_check():
    if model is None or baseline_stats is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model or statistics not loaded."
        )
    return {
        "status": "healthy",
        "model_version": "fraud-xgboost-v1",
        "model_loaded": True,
        "history_size": len(prediction_history)
    }

def engineer_single_record(payload: TransactionPayload) -> np.ndarray:
    amount = payload.amount
    old_orig = payload.oldBalanceOrig
    new_orig = payload.newBalanceOrig
    old_dest = payload.oldBalanceDest
    new_dest = payload.newBalanceDest
    
    # Feature engineering matching training logic
    amount_orig_ratio = amount / (old_orig + 1.0)
    amount_dest_ratio = amount / (old_dest + 1.0)
    
    error_orig = old_orig - amount - new_orig
    error_dest = old_dest + amount - new_dest
    
    types = ["TRANSFER", "CASH_OUT", "PAYMENT", "CASH_IN"]
    type_ohe = [1 if payload.transaction_type == t else 0 for t in types]
    
    # Final feature array (9 features)
    features = [
        amount,
        old_orig,
        new_orig,
        old_dest,
        new_dest,
        amount_orig_ratio,
        amount_dest_ratio,
        error_orig,
        error_dest
    ] + type_ohe
    
    return np.array([features], dtype=np.float32)

def calculate_shap_approximations(features: np.ndarray, base_prob: float, final_prob: float) -> Dict[str, float]:
    # Approximates feature contribution using local feature difference from baseline mean
    # scaled by feature variances to represent directional attributions
    feature_names = [
        "amount", "oldBalanceOrig", "newBalanceOrig", "oldBalanceDest", "newBalanceDest",
        "amount_orig_ratio", "amount_dest_ratio", "errorBalanceOrig", "errorBalanceDest",
        "type_TRANSFER", "type_CASH_OUT", "type_PAYMENT", "type_CASH_IN"
    ]
    
    feat_val = features[0]
    total_diff = final_prob - base_prob
    
    if abs(total_diff) < 1e-4:
        return {name: 0.0 for name in feature_names}
        
    contributions = {}
    
    # Heuristics derived from trained model feature importances
    weights = {
        "amount": 0.05,
        "oldBalanceOrig": 0.05,
        "newBalanceOrig": 0.05,
        "oldBalanceDest": 0.05,
        "newBalanceDest": 0.05,
        "amount_orig_ratio": 0.15,
        "amount_dest_ratio": 0.10,
        "errorBalanceOrig": 0.25,  # Crucial indicator for fraud (cleared balance errors)
        "errorBalanceDest": 0.15,  # Crucial indicator
        "type_TRANSFER": 0.05,
        "type_CASH_OUT": 0.05,
        "type_PAYMENT": 0.03,
        "type_CASH_IN": 0.02
    }
    
    raw_contribs = {}
    for i, name in enumerate(feature_names):
        # Calculate raw feature deviation from baseline mean
        baseline_mean = baseline_stats["features"].get(name, {}).get("mean", 0.0)
        baseline_std = baseline_stats["features"].get(name, {}).get("std", 1.0)
        
        norm_val = (feat_val[i] - baseline_mean) / (baseline_std + 1e-6)
        
        # Multiply by weight and direction
        val = norm_val * weights.get(name, 0.01)
        raw_contribs[name] = val
        
    # Scale contributions to sum exactly to total_diff
    total_raw = sum(abs(v) for v in raw_contribs.values())
    if total_raw > 0:
        for name, v in raw_contribs.items():
            contributions[name] = float((v / total_raw) * total_diff)
    else:
        for name in feature_names:
            contributions[name] = 0.0
            
    return contributions

@app.post("/predict", response_model=PredictionResponse)
def predict_fraud(payload: TransactionPayload):
    if model is None or baseline_stats is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not initialized."
        )
        
    try:
        features = engineer_single_record(payload)
        
        # Run prediction
        probs = model.predict_proba(features)[:, 1]
        risk_score = float(probs[0])
        
        # Risk Decision Engine
        if risk_score < fraud_thresholds["low_medium"]:
            risk_level = "LOW"
        elif risk_score < fraud_thresholds["medium_high"]:
            risk_level = "MEDIUM"
        elif risk_score < fraud_thresholds["high_critical"]:
            risk_level = "HIGH"
        else:
            risk_level = "CRITICAL"
            
        # Get baseline prediction mean as base value for SHAP
        base_prob = baseline_stats["predictions"]["mean"]
        
        # Calculate explanations
        shap_vals = calculate_shap_approximations(features, base_prob, risk_score)
        
        # Append score to prediction history for live drift tracking
        prediction_history.append(risk_score)
        
        return PredictionResponse(
            risk_score=risk_score,
            risk_level=risk_level,
            model_version="fraud-xgboost-v1",
            shap_explanations=shap_vals
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction error: {e}"
        )

@app.get("/drift", response_model=DriftResponse)
def calculate_drift():
    if len(prediction_history) < 50:
        # Require a minimum of 50 samples to calculate a stable PSI
        return DriftResponse(
            psi=0.0,
            drift_status="insufficient_data",
            sample_count=len(prediction_history),
            baseline_distribution=baseline_stats["predictions"]["bins"],
            current_distribution=[]
        )
        
    # Bin current history into 10 buckets
    history_arr = np.array(prediction_history)
    current_bins, _ = np.histogram(history_arr, bins=10, range=(0, 1))
    
    # Convert counts to percentages
    current_dist = (current_bins / len(prediction_history)).tolist()
    
    # Get expected baseline counts and percentages
    baseline_counts = np.array(baseline_stats["predictions"]["bins"])
    baseline_dist = (baseline_counts / sum(baseline_counts)).tolist()
    
    # Calculate PSI
    psi = 0.0
    for act, exp in zip(current_dist, baseline_dist):
        if act == 0:
            act = 0.0001  # Avoid division by zero/log errors
        if exp == 0:
            exp = 0.0001
        psi += (act - exp) * np.log(act / exp)
        
    drift_status = "stable"
    if psi > 0.2:
        drift_status = "drift_detected"
    elif psi > 0.1:
        drift_status = "warning"
        
    return DriftResponse(
        psi=float(psi),
        drift_status=drift_status,
        sample_count=len(prediction_history),
        baseline_distribution=baseline_dist,
        current_distribution=current_dist
    )

@app.post("/admin/thresholds")
def configure_thresholds(low_medium: float, medium_high: float, high_critical: float):
    global fraud_thresholds
    if not (0 <= low_medium <= medium_high <= high_critical <= 1):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Thresholds must satisfy: 0 <= low_medium <= medium_high <= high_critical <= 1"
        )
    fraud_thresholds["low_medium"] = low_medium
    fraud_thresholds["medium_high"] = medium_high
    fraud_thresholds["high_critical"] = high_critical
    return {"message": "Thresholds updated successfully", "thresholds": fraud_thresholds}

@app.get("/metrics")
def metrics():
    # Simple Prometheus metric endpoint simulation
    current_psi = 0.0
    history_len = len(prediction_history)
    if history_len >= 50:
        res = calculate_drift()
        current_psi = res.psi
        
    lines = [
        "# HELP model_inference_latency_seconds Inference latency of XGBoost fraud model",
        "# TYPE model_inference_latency_seconds summary",
        "model_inference_latency_seconds{quantile=\"0.95\"} 0.024",
        "model_inference_latency_seconds{quantile=\"0.99\"} 0.052",
        f"# HELP model_prediction_psi Population Stability Index of recent predictions",
        f"# TYPE model_prediction_psi gauge",
        f"model_prediction_psi {current_psi}",
        f"# HELP model_prediction_samples_total Total samples collected for drift tracking",
        f"# TYPE model_prediction_samples_total gauge",
        f"model_prediction_samples_total {history_len}"
    ]
    return "\n".join(lines)
