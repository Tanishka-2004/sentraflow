"""
Data Standardisation and Cleaning Functions for SentraFlow Silver Layer.
"""

from typing import Any

import pandas as pd

# ISO 3166-2:IN state codes mapping
INDIAN_STATE_ISO_MAP = {
    "Maharashtra": "IN-MH",
    "Delhi": "IN-DL",
    "Karnataka": "IN-KA",
    "Telangana": "IN-TG",
    "Tamil Nadu": "IN-TN",
    "West Bengal": "IN-WB",
    "Gujarat": "IN-GJ",
    "Rajasthan": "IN-RJ",
    "Uttar Pradesh": "IN-UP",
    "Kerala": "IN-KL",
    "Punjab": "IN-PB",
    "Haryana": "IN-HR",
    "Madhya Pradesh": "IN-MP",
    "Bihar": "IN-BR",
}


def clean_phone_e164(phone: Any) -> str | None:
    """
    Standardises phone numbers to E.164 Indian format (+91XXXXXXXXXX)
    while preserving masked tokens.
    """
    if phone is None or pd.isna(phone):
        return None
    s = str(phone).strip()
    if s.startswith("+91"):
        return s
    # If 10 digits
    digits_and_x = "".join(c for c in s if c.isdigit() or c == "X")
    if len(digits_and_x) == 10:
        return f"+91{digits_and_x}"
    return s


def clean_state_iso(state: Any) -> str | None:
    """
    Standardises Indian state names to ISO 3166-2:IN codes.
    """
    if state is None or pd.isna(state):
        return None
    s = str(state).strip()
    return INDIAN_STATE_ISO_MAP.get(s, s)


def clean_timestamp_utc(ts: Any) -> str | None:
    """
    Normalises timestamps to UTC ISO-8601 format.
    """
    if ts is None or pd.isna(ts):
        return None
    try:
        dt = pd.to_datetime(ts, utc=True)
        return dt.isoformat()
    except Exception:  # noqa: BLE001
        return str(ts)


def clean_amount(amount: Any) -> float:
    """
    Casts amount to rounded positive float.
    """
    try:
        val = float(amount)
        return round(val, 2)
    except Exception:  # noqa: BLE001
        return 0.0
