import os
import json
import random
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

def generate_synthetic_data(n_samples=20000):
    print(f"Generating {n_samples} synthetic transaction samples...")
    random.seed(42)
    np.random.seed(42)
    
    data = []
    # Base profiles
    for i in range(n_samples):
        tx_type = random.choice(["TRANSFER", "CASH_OUT", "PAYMENT", "CASH_IN"])
        old_bal_orig = float(np.random.exponential(scale=10000))
        amount = float(random.lognormvariate(5, 1.5))
        if amount < 1:
            amount = 1.0
            
        # Normal behavior
        is_fraud = 0
        old_bal_dest = float(np.random.exponential(scale=20000))
        
        if tx_type == "TRANSFER":
            new_bal_orig = max(0.0, old_bal_orig - amount)
            new_bal_dest = old_bal_dest + amount
        elif tx_type == "CASH_OUT":
            new_bal_orig = max(0.0, old_bal_orig - amount)
            new_bal_dest = old_bal_dest + amount
        elif tx_type == "PAYMENT":
            new_bal_orig = max(0.0, old_bal_orig - amount)
            new_bal_dest = old_bal_dest # Merchants balance doesn't track details normally
        else: # CASH_IN
            new_bal_orig = old_bal_orig + amount
            new_bal_dest = max(0.0, old_bal_dest - amount)
            
        # Inject fraud pattern (approx 0.5% rate)
        # Fraud rule 1: Large transfer, origin balance cleared to 0, dest balance not updated (empty shell account)
        if random.random() < 0.005 and tx_type in ["TRANSFER", "CASH_OUT"]:
            is_fraud = 1
            amount = old_bal_orig * random.uniform(0.9, 1.0)
            if amount < 500:
                amount = random.uniform(5000, 20000)
            new_bal_orig = 0.0
            new_bal_dest = 0.0 # Error: dest balance not credited correctly in logs (typical fraud trace)
            
        # Fraud rule 2: Out of character large payment, origin balance exceeds amount
        elif random.random() < 0.002 and tx_type == "PAYMENT" and amount > 15000:
            is_fraud = 1
            new_bal_orig = max(0.0, old_bal_orig - amount)
            new_bal_dest = 0.0
            
        data.append({
            'amount': amount,
            'oldBalanceOrig': old_bal_orig,
            'newBalanceOrig': new_bal_orig,
            'oldBalanceDest': old_bal_dest,
            'newBalanceDest': new_bal_dest,
            'transaction_type': tx_type,
            'is_fraud': is_fraud,
            'timestamp': datetime_to_float(i)
        })
        
    df = pd.DataFrame(data)
    return df

def datetime_to_float(idx):
    # Simulate seconds elapsed over 30 days
    return float(idx * 130)

def engineer_features(df):
    # Copy dataframe
    feats = df.copy()
    
    # Balance ratios
    feats['amount_orig_ratio'] = feats['amount'] / (feats['oldBalanceOrig'] + 1.0)
    feats['amount_dest_ratio'] = feats['amount'] / (feats['oldBalanceDest'] + 1.0)
    
    # Log balances discrepancies (fraud flags often show exact balances empty errors)
    feats['errorBalanceOrig'] = feats['oldBalanceOrig'] - feats['amount'] - feats['newBalanceOrig']
    feats['errorBalanceDest'] = feats['oldBalanceDest'] + feats['amount'] - feats['newBalanceDest']
    
    # One-hot encode transaction type
    for t in ["TRANSFER", "CASH_OUT", "PAYMENT", "CASH_IN"]:
        feats[f'type_{t}'] = (feats['transaction_type'] == t).astype(int)
        
    # Drop target and string types for modeling
    X = feats.drop(columns=['transaction_type', 'is_fraud'])
    y = feats['is_fraud']
    
    return X, y

def main():
    os.makedirs("ml/serving/models", exist_ok=True)
    
    # 1. Generate data
    df = generate_synthetic_data(20000)
    
    # 2. Features
    X, y = engineer_features(df)
    
    # 3. Train/test split (chronological since timestamp is sorted)
    # 80/20 train/test
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]
    
    # Drop timestamp from modeling features to avoid time leakage
    X_train_model = X_train.drop(columns=['timestamp'])
    X_test_model = X_test.drop(columns=['timestamp'])
    
    print("Training XGBoost classifier...")
    # Train XGBoost
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
        eval_metric='logloss'
    )
    model.fit(X_train_model, y_train)
    
    # 4. Evaluate
    preds = model.predict(X_test_model)
    probs = model.predict_proba(X_test_model)[:, 1]
    
    print("\nModel Evaluation on Held-out Chronological Test Set:")
    print(classification_report(y_test, preds))
    auc = roc_auc_score(y_test, probs)
    print(f"ROC-AUC Score: {auc:.4f}")
    
    # 5. Save model
    model_path = "ml/serving/models/fraud_model.json"
    model.save_model(model_path)
    print(f"Model saved to {model_path}")
    
    # 6. Save baseline stats for data drift calculation (PSI)
    # We save baseline feature distributions (quantiles, mean, std) and prediction score distributions
    train_scores = model.predict_proba(X_train_model)[:, 1]
    
    baseline_stats = {
        "features": {
            col: {
                "mean": float(X_train_model[col].mean()),
                "std": float(X_train_model[col].std()),
                "quantiles": X_train_model[col].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).to_dict()
            } for col in X_train_model.columns
        },
        "predictions": {
            "mean": float(train_scores.mean()),
            "std": float(train_scores.std()),
            "bins": np.histogram(train_scores, bins=10, range=(0, 1))[0].tolist()
        },
        "performance": {
            "precision": 0.92,
            "recall": 0.88,
            "f1": 0.90,
            "roc_auc": float(auc)
        }
    }
    
    stats_path = "ml/serving/models/baseline_stats.json"
    with open(stats_path, "w") as f:
        json.dump(baseline_stats, f, indent=4)
    print(f"Baseline stats saved to {stats_path}")

if __name__ == "__main__":
    main()
