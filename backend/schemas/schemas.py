from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

# -----------------------------------------------------
# Auth & User Schemas
# -----------------------------------------------------

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str = Field(..., pattern="^(analyst|admin|auditor)$")

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class TokenData(BaseModel):
    email: Optional[str] = None
    role: Optional[str] = None

# -----------------------------------------------------
# Model Registry & Drift Schemas
# -----------------------------------------------------

class ModelRegistryResponse(BaseModel):
    id: int
    model_version: str
    training_dataset_version: str
    feature_version: str
    trained_at: datetime
    precision: float
    recall: float
    f1: float
    roc_auc: float
    status: str
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    deployment_status: str
    drift_status: str
    
    class Config:
        from_attributes = True

class ModelDriftMetricResponse(BaseModel):
    id: int
    model_version: str
    metric_name: str
    metric_value: float
    threshold: float
    is_drifted: bool
    checked_at: datetime
    
    class Config:
        from_attributes = True

# -----------------------------------------------------
# Data Catalog Schemas
# -----------------------------------------------------

class CatalogColumnResponse(BaseModel):
    id: int
    dataset_id: int
    name: str
    data_type: str
    description: Optional[str] = None
    is_pii: bool
    sensitivity: Optional[str] = None
    masking_strategy: str
    
    class Config:
        from_attributes = True

class CatalogDatasetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    owner: Optional[str] = None
    storage_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    columns: List[CatalogColumnResponse] = []
    
    class Config:
        from_attributes = True

# -----------------------------------------------------
# PII Governance Rules Schemas
# -----------------------------------------------------

class PiiRuleCreate(BaseModel):
    column_pattern: str
    rule_type: str = Field(..., pattern="^(regex|classifier)$")
    masking_strategy: str = Field(..., pattern="^(hash|tokenize|redact)$")

class PiiRuleResponse(BaseModel):
    id: int
    column_pattern: str
    rule_type: str
    masking_strategy: str
    created_by: Optional[int] = None
    created_at: datetime
    active: bool
    
    class Config:
        from_attributes = True

# -----------------------------------------------------
# Pipeline Run Schemas
# -----------------------------------------------------

class PipelineRunResponse(BaseModel):
    run_id: str
    pipeline_version: str
    code_version: str
    schema_version: str
    model_version: Optional[str] = None
    input_snapshot: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: Optional[str] = None
    bronze_status: Optional[str] = None
    silver_status: Optional[str] = None
    pii_status: Optional[str] = None
    dq_status: Optional[str] = None
    gold_status: Optional[str] = None
    
    class Config:
        from_attributes = True

class PipelineRunsListResponse(BaseModel):
    runs: List[PipelineRunResponse]
    total: int
    page: int
    limit: int

# -----------------------------------------------------
# Alerts & Transactions Schemas
# -----------------------------------------------------

class AlertUpdate(BaseModel):
    status: str = Field(..., pattern="^(resolved|false_positive)$")
    reason: str = Field(..., min_length=5, description="Auditable justification for change")

class AlertResponse(BaseModel):
    id: int
    transaction_id: str
    risk_score: float
    risk_level: str
    status: str
    resolved_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

class AlertsListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    page: int
    limit: int

class TransactionResponse(BaseModel):
    transaction_id: str
    account_id: str
    date_key: int
    amount: float
    transaction_type: str
    risk_score: float
    is_flagged: bool
    source: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class TransactionsListResponse(BaseModel):
    transactions: List[TransactionResponse]
    total: int
    page: int
    limit: int

# -----------------------------------------------------
# Lineage Schemas
# -----------------------------------------------------

class LineageNode(BaseModel):
    id: str
    label: str
    type: str # 'table' or 'column'

class LineageEdge(BaseModel):
    source: str
    target: str
    id: str

class LineageResponse(BaseModel):
    nodes: List[LineageNode]
    edges: List[LineageEdge]

# -----------------------------------------------------
# Audit Logs Schemas
# -----------------------------------------------------

class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int] = None
    action: str
    resource: str
    target_id: Optional[int] = None
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    reason: str
    ip_address: str
    user_agent: str
    timestamp: datetime
    
    class Config:
        from_attributes = True

class AuditLogListResponse(BaseModel):
    logs: List[AuditLogResponse]
    total: int
    page: int
    limit: int
