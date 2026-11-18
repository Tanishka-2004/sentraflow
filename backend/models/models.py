from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Numeric, Table
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from backend.core.database import Base

# -----------------------------------------------------
# Metadata Schema Models (public schema)
# -----------------------------------------------------

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False) # 'analyst', 'admin', 'auditor'
    created_at = Column(DateTime, default=datetime.utcnow)

class ModelRegistry(Base):
    __tablename__ = "model_registry"
    
    id = Column(Integer, primary_key=True, index=True)
    model_version = Column(String(50), unique=True, nullable=False)
    training_dataset_version = Column(String(100), nullable=False)
    feature_version = Column(String(100), nullable=False)
    trained_at = Column(DateTime, default=datetime.utcnow)
    precision = Column(Float, nullable=False)
    recall = Column(Float, nullable=False)
    f1 = Column(Float, nullable=False)
    roc_auc = Column(Float, nullable=False)
    status = Column(String(50), nullable=False) # 'development', 'staging', 'production', 'archived'
    approved_by = Column(String(100))
    approved_at = Column(DateTime)
    deployment_status = Column(String(50), nullable=False) # 'active', 'inactive'
    drift_status = Column(String(50), default="stable") # 'stable', 'drift_detected'
    
    drift_metrics = relationship("ModelDriftMetric", back_populates="model")

class ModelDriftMetric(Base):
    __tablename__ = "model_drift_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    model_version = Column(String(50), ForeignKey("model_registry.model_version", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    is_drifted = Column(Boolean, default=False)
    checked_at = Column(DateTime, default=datetime.utcnow)
    
    model = relationship("ModelRegistry", back_populates="drift_metrics")

class CatalogDataset(Base):
    __tablename__ = "catalog_datasets"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    owner = Column(String(100))
    storage_path = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    columns = relationship("CatalogColumn", back_populates="dataset", cascade="all, delete-orphan")

class CatalogColumn(Base):
    __tablename__ = "catalog_columns"
    
    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("catalog_datasets.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    data_type = Column(String(50), nullable=False)
    description = Column(Text)
    is_pii = Column(Boolean, default=False)
    sensitivity = Column(String(50)) # 'low', 'medium', 'high', 'critical'
    masking_strategy = Column(String(50), default="none")
    
    dataset = relationship("CatalogDataset", back_populates="columns")

class PiiRule(Base):
    __tablename__ = "pii_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    column_pattern = Column(String(100), nullable=False)
    rule_type = Column(String(50), nullable=False) # 'regex', 'classifier'
    masking_strategy = Column(String(50), nullable=False) # 'hash', 'tokenize', 'redact'
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    active = Column(Boolean, default=True)

class PipelineRun(Base):
    __tablename__ = "pipeline_runs"
    
    run_id = Column(String(100), primary_key=True)
    pipeline_version = Column(String(50), nullable=False)
    code_version = Column(String(50), nullable=False)
    schema_version = Column(String(50), nullable=False)
    model_version = Column(String(50), ForeignKey("model_registry.model_version"))
    input_snapshot = Column(String(255), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    status = Column(String(50)) # 'running', 'success', 'failed'
    bronze_status = Column(String(50))
    silver_status = Column(String(50))
    pii_status = Column(String(50)) # 'pending', 'running', 'success', 'failed_closed'
    dq_status = Column(String(50))
    gold_status = Column(String(50))

class Alert(Base):
    __tablename__ = "alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(String(100), unique=True, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False) # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    status = Column(String(50), nullable=False) # 'open', 'resolved', 'false_positive'
    resolved_by = Column(Integer, ForeignKey("users.id"))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

class LineageEvent(Base):
    __tablename__ = "lineage_events"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), nullable=False)
    step_name = Column(String(100), nullable=False)
    source_table = Column(String(100), nullable=False)
    source_column = Column(String(100))
    target_table = Column(String(100), nullable=False)
    target_column = Column(String(100))
    event_type = Column(String(50), nullable=False) # 'read', 'transform', 'write'
    timestamp = Column(DateTime, default=datetime.utcnow)

class DqResult(Base):
    __tablename__ = "dq_results"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), nullable=False)
    test_name = Column(String(255), nullable=False)
    model_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False) # 'pass', 'fail'
    details = Column(JSONB)
    timestamp = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=False)
    target_id = Column(Integer)
    before_state = Column(JSONB)
    after_state = Column(JSONB)
    reason = Column(Text, nullable=False)
    ip_address = Column(String(45), nullable=False)
    user_agent = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

# -----------------------------------------------------
# Warehouse Schema Models (warehouse schema)
# -----------------------------------------------------

class DimCustomer(Base):
    __tablename__ = "dim_customer"
    __table_args__ = {"schema": "warehouse"}
    
    customer_key = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255))
    phone = Column(String(50))
    address = Column(String(255))
    scd_effective_from = Column(DateTime, nullable=False)
    scd_effective_to = Column(DateTime)
    is_current = Column(Boolean, default=True)

class DimAccount(Base):
    __tablename__ = "dim_account"
    __table_args__ = {"schema": "warehouse"}
    
    account_key = Column(Integer, primary_key=True, index=True)
    account_id = Column(String(100), unique=True, nullable=False, index=True)
    customer_id = Column(String(100), nullable=False)
    account_type = Column(String(50))
    opened_date = Column(DateTime)

class DimTime(Base):
    __tablename__ = "dim_time"
    __table_args__ = {"schema": "warehouse"}
    
    date_key = Column(Integer, primary_key=True)
    date = Column(DateTime, unique=True, nullable=False)
    day_of_week = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)

class FactTransaction(Base):
    __tablename__ = "fact_transactions"
    __table_args__ = {"schema": "warehouse"}
    
    transaction_id = Column(String(100), primary_key=True)
    account_id = Column(String(100), nullable=False, index=True)
    date_key = Column(Integer, nullable=False, index=True)
    amount = Column(Numeric(15, 2), nullable=False)
    transaction_type = Column(String(50), nullable=False)
    risk_score = Column(Float, default=0.0)
    is_flagged = Column(Boolean, default=False, index=True)
    source = Column(String(20)) # 'batch', 'stream'
    created_at = Column(DateTime, default=datetime.utcnow)
