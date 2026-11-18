"""
Pydantic data models for synthetic banking entities.
"""

from pydantic import BaseModel


class Customer(BaseModel):
    customer_id: str
    full_name: str
    email: str | None = None
    phone: str | None = None
    pan: str | None = None
    aadhaar_id: str | None = None
    date_of_birth: str
    address: str
    city: str
    state: str
    pincode: str
    kyc_status: str  # PENDING, VERIFIED, REJECTED
    created_at: str
    updated_at: str


class Account(BaseModel):
    account_id: str
    customer_id: str
    account_number: str
    ifsc: str
    account_type: str  # SAVINGS, CURRENT, SALARY
    open_date: str
    status: str  # ACTIVE, DORMANT, FROZEN
    balance: float


class Merchant(BaseModel):
    merchant_id: str
    name: str
    mcc_code: str
    city: str
    risk_tier: str  # LOW, MEDIUM, HIGH, CRITICAL


class Transaction(BaseModel):
    txn_id: str
    account_id: str
    merchant_id: str
    amount: float
    currency: str = "INR"
    channel: str  # UPI, CARD, NEFT, IMPS, ATM
    txn_ts: str
    device_id: str | None = None
    ip_address: str | None = None
    lat: float
    lon: float
    status: str  # SUCCESS, PENDING, FAILED
    is_fraud: int = 0  # 0 or 1 (hidden evaluation label)
    fraud_pattern: str | None = None
    promo_code: str | None = None  # Schema drift optional field
