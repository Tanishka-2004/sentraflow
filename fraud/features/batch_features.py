"""
Batch Feature Store for SentraFlow Fraud Engine.

Extracts and maintains customer 30-day baseline statistics and merchant risk profiles
from Silver/Gold lakehouse tables or cached reference profiles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Dict, Optional
import pandas as pd


@dataclass
class CustomerProfile:
    customer_id: str
    avg_ticket_size: float = 2500.0
    std_ticket_size: float = 1200.0
    txn_count_30d: int = 25
    home_city: str = "Mumbai"
    home_lat: float = 19.0760
    home_lon: float = 72.8777
    known_devices: set[str] = field(default_factory=set)
    last_txn_ts: Optional[datetime] = None
    last_lat: Optional[float] = None
    last_lon: Optional[float] = None


@dataclass
class MerchantProfile:
    merchant_id: str
    name: str = "Merchant"
    risk_tier: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    risk_score: float = 0.05
    chargeback_rate: float = 0.005
    mcc_code: str = "5411"


class BatchFeatureStore:
    """Manages batch-computed profiles for customers and merchants."""

    def __init__(self) -> None:
        self._customers: dict[str, CustomerProfile] = {}
        self._merchants: dict[str, MerchantProfile] = {}
        self._risk_tier_weights = {
            "LOW": 0.05,
            "MEDIUM": 0.25,
            "HIGH": 0.65,
            "CRITICAL": 0.95,
        }

    def register_customer(
        self,
        customer_id: str,
        avg_ticket_size: float = 2500.0,
        std_ticket_size: float = 1200.0,
        txn_count_30d: int = 25,
        home_city: str = "Mumbai",
        home_lat: float = 19.0760,
        home_lon: float = 72.8777,
        initial_devices: Optional[list[str]] = None,
    ) -> CustomerProfile:
        devices = set(initial_devices or [])
        profile = CustomerProfile(
            customer_id=customer_id,
            avg_ticket_size=max(10.0, float(avg_ticket_size)),
            std_ticket_size=max(1.0, float(std_ticket_size)),
            txn_count_30d=max(1, int(txn_count_30d)),
            home_city=home_city,
            home_lat=home_lat,
            home_lon=home_lon,
            known_devices=devices,
        )
        self._customers[customer_id] = profile
        return profile

    def register_merchant(
        self,
        merchant_id: str,
        name: str = "Merchant",
        risk_tier: str = "LOW",
        chargeback_rate: float = 0.005,
        mcc_code: str = "5411",
    ) -> MerchantProfile:
        tier = risk_tier.upper() if risk_tier else "LOW"
        risk_score = self._risk_tier_weights.get(tier, 0.1)
        profile = MerchantProfile(
            merchant_id=merchant_id,
            name=name,
            risk_tier=tier,
            risk_score=risk_score,
            chargeback_rate=float(chargeback_rate),
            mcc_code=mcc_code,
        )
        self._merchants[merchant_id] = profile
        return profile

    def get_customer(self, customer_id: str) -> CustomerProfile:
        if customer_id not in self._customers:
            # Default cold-start customer profile
            self._customers[customer_id] = CustomerProfile(
                customer_id=customer_id,
                avg_ticket_size=2000.0,
                std_ticket_size=1000.0,
                txn_count_30d=10,
                home_city="Mumbai",
                home_lat=19.0760,
                home_lon=72.8777,
            )
        return self._customers[customer_id]

    def get_merchant(self, merchant_id: str) -> MerchantProfile:
        if merchant_id not in self._merchants:
            # Default cold-start merchant profile
            self._merchants[merchant_id] = MerchantProfile(
                merchant_id=merchant_id,
                name=f"Merchant_{merchant_id[:8]}",
                risk_tier="LOW",
                risk_score=0.1,
                chargeback_rate=0.005,
                mcc_code="5411",
            )
        return self._merchants[merchant_id]

    def populate_from_dataframes(
        self,
        customers_df: Optional[pd.DataFrame] = None,
        merchants_df: Optional[pd.DataFrame] = None,
        txns_df: Optional[pd.DataFrame] = None,
    ) -> None:
        """Hydrate feature store from Silver/Gold DataFrames."""
        if merchants_df is not None and not merchants_df.empty:
            for _, row in merchants_df.iterrows():
                mid = str(row.get("merchant_id", ""))
                if mid:
                    self.register_merchant(
                        merchant_id=mid,
                        name=str(row.get("name", "Merchant")),
                        risk_tier=str(row.get("risk_tier", "LOW")),
                        mcc_code=str(row.get("mcc_code", "5411")),
                    )

        if customers_df is not None and not customers_df.empty:
            for _, row in customers_df.iterrows():
                cid = str(row.get("customer_id", ""))
                if cid:
                    self.register_customer(
                        customer_id=cid,
                        home_city=str(row.get("city", "Mumbai")),
                    )

        if txns_df is not None and not txns_df.empty:
            grouped = txns_df.groupby("account_id")
            for acc_id, group in grouped:
                avg_amt = float(group["amount"].mean())
                std_amt = float(group["amount"].std()) if len(group) > 1 else avg_amt * 0.5
                cid = str(group.iloc[0].get("customer_id", acc_id))
                cust = self.get_customer(cid)
                cust.avg_ticket_size = avg_amt
                cust.std_ticket_size = std_amt if not math.isnan(std_amt) and std_amt > 0 else 100.0
                cust.txn_count_30d = len(group)
                devices = set(group["device_id"].dropna().astype(str).unique())
                cust.known_devices.update(devices)

