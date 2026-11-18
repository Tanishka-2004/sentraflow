"""
Streaming and Rolling Feature Calculator for Real-Time Fraud Detection.

Computes sliding window metrics, geospatial velocity (Haversine & implied speed),
device novelty, and behavioral z-scores with sub-millisecond execution.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple

from fraud.features.batch_features import BatchFeatureStore, CustomerProfile, MerchantProfile


EARTH_RADIUS_KM = 6371.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate Great Circle distance between two lat/lon points using Haversine formula."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return EARTH_RADIUS_KM * c


@dataclass
class TxnHistoryRecord:
    txn_id: str
    amount: float
    timestamp: datetime
    lat: float
    lon: float
    device_id: str


class StreamingFeatureStore:
    """
    In-memory rolling window cache per customer/account for real-time feature derivation.
    Maintains clean 60-minute sliding histories with fast eviction.
    """

    def __init__(self, batch_store: Optional[BatchFeatureStore] = None) -> None:
        self.batch_store = batch_store or BatchFeatureStore()
        # customer_id -> deque of recent TxnHistoryRecord
        self._history: dict[str, deque[TxnHistoryRecord]] = {}

    def _get_history(self, customer_id: str) -> deque[TxnHistoryRecord]:
        if customer_id not in self._history:
            self._history[customer_id] = deque()
        return self._history[customer_id]

    def _evict_stale(self, history: deque[TxnHistoryRecord], current_ts: datetime, window_seconds: float = 3600.0) -> None:
        cutoff = current_ts.timestamp() - window_seconds
        while history and history[0].timestamp.timestamp() < cutoff:
            history.popleft()

    def compute_features(
        self,
        customer_id: str,
        account_id: str,
        merchant_id: str,
        amount: float,
        channel: str,
        txn_ts: datetime,
        lat: float,
        lon: float,
        device_id: str,
        update_state: bool = True,
    ) -> dict[str, float]:
        """
        Derive the complete set of numeric features required by the XGBoost fraud classifier.
        """
        # Ensure UTC timezone
        if txn_ts.tzinfo is None:
            txn_ts = txn_ts.replace(tzinfo=timezone.utc)

        cust_profile = self.batch_store.get_customer(customer_id)
        merch_profile = self.batch_store.get_merchant(merchant_id)

        history = self._get_history(customer_id)
        self._evict_stale(history, txn_ts, window_seconds=3600.0)

        # Rolling window counts & sums
        current_epoch = txn_ts.timestamp()
        count_1m = 0
        count_5m = 0
        count_60m = len(history)
        amount_sum_10m = 0.0

        for rec in reversed(history):
            delta_sec = current_epoch - rec.timestamp.timestamp()
            if delta_sec <= 60:
                count_1m += 1
            if delta_sec <= 300:
                count_5m += 1
            if delta_sec <= 600:
                amount_sum_10m += rec.amount

        # Behavioral amount z-score against 30-day baseline
        avg_ticket = cust_profile.avg_ticket_size
        std_ticket = cust_profile.std_ticket_size
        amount_zscore = (amount - avg_ticket) / max(1.0, std_ticket)

        # Geospatial velocity and impossible travel
        dist_km = 0.0
        implied_speed_kmh = 0.0
        is_impossible_travel = 0.0

        if history:
            last_rec = history[-1]
            dist_km = haversine_distance_km(last_rec.lat, last_rec.lon, lat, lon)
            delta_hours = max(0.00027, (current_epoch - last_rec.timestamp.timestamp()) / 3600.0)  # min 1s
            implied_speed_kmh = dist_km / delta_hours

            # If velocity exceeds commercial airliner speed (> 800 km/h) over non-trivial distance
            if implied_speed_kmh > 800.0 and dist_km > 30.0:
                is_impossible_travel = 1.0
        elif cust_profile.last_lat is not None and cust_profile.last_lon is not None:
            dist_km = haversine_distance_km(cust_profile.last_lat, cust_profile.last_lon, lat, lon)

        # Device novelty check
        is_new_device = 1.0 if device_id not in cust_profile.known_devices else 0.0

        # Temporal patterns
        hour_of_day = float(txn_ts.hour)
        is_night_txn = 1.0 if hour_of_day in [0.0, 1.0, 2.0, 3.0, 4.0] else 0.0
        is_high_value_night = 1.0 if (is_night_txn and amount > 10000.0) else 0.0

        # Channel risk mapping
        channel_codes = {"UPI": 1.0, "CARD": 2.0, "NEFT": 3.0, "IMPS": 4.0, "ATM": 5.0}
        channel_code = channel_codes.get(channel.upper(), 1.0)

        # Velocity burst indicator (many txns in 5 minutes)
        is_velocity_burst = 1.0 if count_5m >= 3 else 0.0

        features = {
            "amount": float(amount),
            "avg_ticket_size": float(avg_ticket),
            "amount_zscore": float(amount_zscore),
            "txn_count_1m": float(count_1m),
            "txn_count_5m": float(count_5m),
            "txn_count_60m": float(count_60m),
            "txn_amount_sum_10m": float(amount_sum_10m),
            "dist_from_last_txn_km": float(dist_km),
            "implied_speed_kmh": float(implied_speed_kmh),
            "is_impossible_travel": float(is_impossible_travel),
            "is_new_device": float(is_new_device),
            "is_high_value_night": float(is_high_value_night),
            "is_velocity_burst": float(is_velocity_burst),
            "merchant_risk_score": float(merch_profile.risk_score),
            "merchant_chargeback_rate": float(merch_profile.chargeback_rate),
            "channel_code": float(channel_code),
            "hour_of_day": float(hour_of_day),
        }

        if update_state:
            # Update customer known devices and rolling deque
            cust_profile.known_devices.add(device_id)
            cust_profile.last_lat = lat
            cust_profile.last_lon = lon
            cust_profile.last_txn_ts = txn_ts

            history.append(
                TxnHistoryRecord(
                    txn_id=customer_id,
                    amount=amount,
                    timestamp=txn_ts,
                    lat=lat,
                    lon=lon,
                    device_id=device_id,
                )
            )

        return features

