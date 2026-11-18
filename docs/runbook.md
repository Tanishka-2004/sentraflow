# SentraFlow Operational Runbook

## 1. Local Environment Setup & Execution

### 1.1 Prerequisites
- Python 3.11+
- Docker Engine & Docker Compose
- Node.js 18+ (for dashboard development)
- Make (optional, shortcuts provided)

### 1.2 Bring up Local Lakehouse Stack
```bash
# 1. Start storage, database, metadata, and services
docker compose up -d

# 2. Seed initial synthetic banking data
make seed
# Or manually:
python -m data_generator.cli --customers 5000 --txns 50000 --landing-dir landing/

# 3. Launch FastAPI backend (Port 8000)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 4. Launch Next.js Dashboard (Port 3001)
cd dashboard && npm run dev
```

---

## 2. Triggering Workflows & Simulating Streaming Fraud

### 2.1 Trigger Batch Pipeline Manually
```bash
# Option A: Via Airflow CLI
airflow dags trigger sentraflow_batch_pipeline

# Option B: Via REST API (Data Engineer or Admin token required)
curl -X POST http://localhost:8000/pipelines/trigger/sentraflow_batch_pipeline \
  -H "Authorization: Bearer <TOKEN>"
```

### 2.2 Simulate Streaming Burst of Fraud Transactions
```bash
# Generates high-velocity bursts and impossible travel attacks into Kafka txn.raw
python -m data_generator.cli --stream --events-per-second 50 --fraud-rate 0.15
```

---

## 3. Cryptographic Key Rotation (HMAC Tokenization)

To rotate the HMAC masking key without breaking historical join relationships:

1. **Provision New KMS Key Version:**
   Generate key version `V2` in AWS KMS / Secrets Manager.
2. **Dual-Key Transformation Phase:**
   Update `policies.yaml`:
   ```yaml
   tokenization:
     active_key_version: "v2"
     fallback_key_version: "v1"
   ```
3. **Backfill Historical Tables:**
   Execute the key migration Spark job:
   ```bash
   python spark_jobs/governance/rotate_keys.py --table silver.customers --target-version v2
   ```
4. **Decommission Fallback:**
   Once `dim_customer` and `fct_transactions` align on `v2`, deprecate `v1`.

---

## 4. Triage & Incident Response: Governance Gate Failures

When a batch fails at the PII Governance Gate:

1. **Inspect Gate Audit Log:**
   ```sql
   SELECT * FROM governance.pii_gate_audit WHERE passed = false ORDER BY executed_at DESC LIMIT 5;
   ```
2. **Review Identified Violations:**
   The gate records the offending table, column name, sample match count, and regex rule.
3. **Root Cause Analysis:**
   - Did upstream core banking add an unclassified column (schema drift)?
   - Did an existing column receive unmasked PAN or phone data?
4. **Resolution:**
   - If an unclassified PII column was introduced: Update `classification_registry.yaml` and `policies.yaml` to specify the required masking policy.
   - Re-run the batch job:
     ```bash
     airflow dags trigger sentraflow_batch_pipeline -c '{"force_reprocess_batch": "BATCH_ID"}'
     ```
5. **Two-Party Bypass Override Procedure:**
   Under strict RBI compliance, bypassing the gate requires cryptographic sign-off from both the **Lead Data Engineer** and the **Chief Compliance Officer** recorded in `governance.emergency_gate_overrides`.

---

## 5. Cloud Deployment Guide (AWS)

```bash
# 1. Provision Infrastructure via Terraform
cd infra/terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# 2. Deploy Airflow DAGs to MWAA S3 Bucket
aws s3 sync airflow/dags/ s3://sentraflow-lakehouse-artifacts-prod/dags/

# 3. Submit Spark Governance Gate to EMR Serverless
aws emr-serverless start-job-run \
  --application-id <EMR_APP_ID> \
  --execution-role-arn arn:aws:iam::123456789012:role/sentraflow-spark-gate-role \
  --job-driver '{
    "sparkSubmit": {
      "entryPoint": "s3://sentraflow-lakehouse-artifacts-prod/jobs/gate.py",
      "entryPointArguments": ["--batch-id", "BATCH_2026_001"]
    }
  }'
```

