-- Create schemas
CREATE SCHEMA IF NOT EXISTS warehouse;

-- -----------------------------------------------------
-- Metadata tables (in public schema)
-- -----------------------------------------------------

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('analyst', 'admin', 'auditor')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Model Registry table
CREATE TABLE IF NOT EXISTS model_registry (
    id SERIAL PRIMARY KEY,
    model_version VARCHAR(50) UNIQUE NOT NULL,
    training_dataset_version VARCHAR(100) NOT NULL,
    feature_version VARCHAR(100) NOT NULL,
    trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    precision FLOAT NOT NULL,
    recall FLOAT NOT NULL,
    f1 FLOAT NOT NULL,
    roc_auc FLOAT NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('development', 'staging', 'production', 'archived')),
    approved_by VARCHAR(100),
    approved_at TIMESTAMP,
    deployment_status VARCHAR(50) NOT NULL CHECK (deployment_status IN ('active', 'inactive')),
    drift_status VARCHAR(50) DEFAULT 'stable' CHECK (drift_status IN ('stable', 'drift_detected'))
);

-- Model Drift Metrics table
CREATE TABLE IF NOT EXISTS model_drift_metrics (
    id SERIAL PRIMARY KEY,
    model_version VARCHAR(50) REFERENCES model_registry(model_version) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    threshold FLOAT NOT NULL,
    is_drifted BOOLEAN DEFAULT FALSE,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Data Catalog Tables
CREATE TABLE IF NOT EXISTS catalog_datasets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    owner VARCHAR(100),
    storage_path VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS catalog_columns (
    id SERIAL PRIMARY KEY,
    dataset_id INT REFERENCES catalog_datasets(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    data_type VARCHAR(50) NOT NULL,
    description TEXT,
    is_pii BOOLEAN DEFAULT FALSE,
    sensitivity VARCHAR(50) CHECK (sensitivity IN ('low', 'medium', 'high', 'critical')),
    masking_strategy VARCHAR(50) DEFAULT 'none',
    CONSTRAINT unique_column_per_dataset UNIQUE (dataset_id, name)
);

-- PII Governance Rules table
CREATE TABLE IF NOT EXISTS pii_rules (
    id SERIAL PRIMARY KEY,
    column_pattern VARCHAR(100) NOT NULL,
    rule_type VARCHAR(50) NOT NULL CHECK (rule_type IN ('regex', 'classifier')),
    masking_strategy VARCHAR(50) NOT NULL CHECK (masking_strategy IN ('hash', 'tokenize', 'redact')),
    created_by INT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    active BOOLEAN DEFAULT TRUE
);

-- Run Versioning table
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id VARCHAR(100) PRIMARY KEY,
    pipeline_version VARCHAR(50) NOT NULL,
    code_version VARCHAR(50) NOT NULL,
    schema_version VARCHAR(50) NOT NULL,
    model_version VARCHAR(50) REFERENCES model_registry(model_version),
    input_snapshot VARCHAR(255) NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(50) CHECK (status IN ('running', 'success', 'failed')),
    bronze_status VARCHAR(50) CHECK (bronze_status IN ('pending', 'running', 'success', 'failed')),
    silver_status VARCHAR(50) CHECK (silver_status IN ('pending', 'running', 'success', 'failed')),
    pii_status VARCHAR(50) CHECK (pii_status IN ('pending', 'running', 'success', 'failed', 'failed_closed')),
    dq_status VARCHAR(50) CHECK (dq_status IN ('pending', 'running', 'success', 'failed')),
    gold_status VARCHAR(50) CHECK (gold_status IN ('pending', 'running', 'success', 'failed'))
);

-- Fraud Alerts table
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(100) UNIQUE NOT NULL,
    risk_score FLOAT NOT NULL,
    risk_level VARCHAR(20) NOT NULL CHECK (risk_level IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    status VARCHAR(50) NOT NULL CHECK (status IN ('open', 'resolved', 'false_positive')),
    resolved_by INT REFERENCES users(id),
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_alerts_status_created ON alerts(status, created_at);

-- Lineage Events table
CREATE TABLE IF NOT EXISTS lineage_events (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL,
    step_name VARCHAR(100) NOT NULL,
    source_table VARCHAR(100) NOT NULL,
    source_column VARCHAR(100),
    target_table VARCHAR(100) NOT NULL,
    target_column VARCHAR(100),
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN ('read', 'transform', 'write')),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_lineage_target ON lineage_events(target_table, target_column);

-- Data Quality Results table
CREATE TABLE IF NOT EXISTS dq_results (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL,
    test_name VARCHAR(255) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('pass', 'fail')),
    details JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Immutable Audit Log table
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    actor_id INT REFERENCES users(id),
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    target_id INT,
    before_state JSONB DEFAULT NULL,
    after_state JSONB DEFAULT NULL,
    reason TEXT NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Trigger to prevent UPDATE or DELETE on audit_log
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Modifications or Deletions of the audit log are strictly prohibited.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_prevent_audit_modification ON audit_log;
CREATE TRIGGER trg_prevent_audit_modification
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();

-- -----------------------------------------------------
-- Warehouse tables (in warehouse schema)
-- -----------------------------------------------------

-- dim_time table
CREATE TABLE IF NOT EXISTS warehouse.dim_time (
    date_key INT PRIMARY KEY,
    date DATE NOT NULL,
    day_of_week INT NOT NULL,
    month INT NOT NULL,
    quarter INT NOT NULL,
    year INT NOT NULL
);

-- dim_customer table
CREATE TABLE IF NOT EXISTS warehouse.dim_customer (
    customer_id VARCHAR(50) PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(100),
    address TEXT,
    scd_effective_from TIMESTAMP NOT NULL,
    scd_effective_to TIMESTAMP,
    is_current BOOLEAN DEFAULT TRUE
);

-- dim_account table
CREATE TABLE IF NOT EXISTS warehouse.dim_account (
    account_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) REFERENCES warehouse.dim_customer(customer_id) ON DELETE CASCADE,
    account_type VARCHAR(50) NOT NULL,
    opened_date DATE NOT NULL
);

-- fact_transactions table
CREATE TABLE IF NOT EXISTS warehouse.fact_transactions (
    transaction_id VARCHAR(100) PRIMARY KEY,
    account_id VARCHAR(50) REFERENCES warehouse.dim_account(account_id) ON DELETE CASCADE,
    date_key INT REFERENCES warehouse.dim_time(date_key),
    amount NUMERIC(15, 2) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    risk_score FLOAT NOT NULL,
    is_flagged BOOLEAN DEFAULT FALSE,
    source VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for transactions query performance
CREATE INDEX IF NOT EXISTS idx_fact_transactions_acc ON warehouse.fact_transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_fact_transactions_date ON warehouse.fact_transactions(date_key);

-- -----------------------------------------------------
-- Sandbox fact table (in public schema for replays)
-- -----------------------------------------------------
CREATE TABLE IF NOT EXISTS public.fact_transactions (
    transaction_id VARCHAR(100) PRIMARY KEY,
    account_id VARCHAR(50),
    date_key INT,
    amount NUMERIC(15, 2) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    risk_score FLOAT NOT NULL,
    is_flagged BOOLEAN DEFAULT FALSE,
    source VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
