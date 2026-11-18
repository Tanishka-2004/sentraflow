"""
PII Masking Engine for SentraFlow.

Applies policy-driven anonymization and pseudonymization techniques:
- Deterministic HMAC-SHA256 Tokenization (joinable across datasets)
- Partial Masking (PAN, Phone, Account)
- Generalization (DOB to Age Bands, Pincode to Region, IP to Subnet)
- Format-Preserving Email Hashing
- Redaction
"""

import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


class PIIMaskingEngine:
    """
    Applies masking transformations to DataFrames according to policies.yaml.
    """

    def __init__(self, policy_path: str | None = None):
        if policy_path is None:
            policy_path = str(Path(__file__).parent / "policies.yaml")

        self.policy_path = policy_path
        self.key_version = "v1"
        self.secret_key = "sentraflow-governance-master-secret-key-local-2026"
        self.rules: dict[str, dict[str, Any]] = {}
        self._load_policy()

    def _load_policy(self):
        p = Path(self.policy_path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.key_version = data.get("key_version", "v1")
                self.secret_key = data.get("default_secret_key", self.secret_key)
                self.rules = data.get("rules", {})

    def hmac_token(self, value: Any) -> str | None:
        """Deterministic joinable tokenization."""
        if value is None or pd.isna(value):
            return None
        val_str = str(value)
        h = hmac.new(
            self.secret_key.encode("utf-8"), val_str.encode("utf-8"), hashlib.sha256
        )
        return f"TOK_{h.hexdigest()[:16]}"

    @staticmethod
    def mask_pan(pan: Any) -> str | None:
        """Partial masking: XXXXX1234X."""
        if pan is None or pd.isna(pan):
            return None
        p = str(pan).strip()
        if len(p) == 10:
            return f"XXXXX{p[5:9]}X"
        return "XXXXXXXXXX"

    @staticmethod
    def mask_phone(phone: Any, keep_last: int = 4) -> str | None:
        """Partial masking: XXXXXX3210."""
        if phone is None or pd.isna(phone):
            return None
        s = "".join(filter(str.isdigit, str(phone)))
        if len(s) >= keep_last:
            masked_part = "X" * (len(s) - keep_last)
            return f"{masked_part}{s[-keep_last:]}"
        return "XXXXXXXXXX"

    @staticmethod
    def mask_account(acc: Any, keep_last: int = 4) -> str | None:
        """Partial masking: XXXXXXXX1234."""
        if acc is None or pd.isna(acc):
            return None
        s = str(acc).strip()
        if len(s) >= keep_last:
            return f"{'X' * (len(s) - keep_last)}{s[-keep_last:]}"
        return "XXXXXXXXXXXX"

    def mask_email(self, email: Any) -> str | None:
        """Format-preserving email hashing: h_{hash[:8]}@domain.com."""
        if email is None or pd.isna(email):
            return None
        s = str(email).strip()
        if "@" in s:
            name, domain = s.split("@", 1)
            h = hashlib.sha256(f"{name}{self.secret_key}".encode()).hexdigest()[:8]
            return f"h_{h}@{domain}"
        return "redacted@sentraflow.internal"

    @staticmethod
    def generalize_dob(dob_str: Any) -> str | None:
        """Generalizes date of birth to age bands."""
        if dob_str is None or pd.isna(dob_str):
            return None
        try:
            birth_date = datetime.strptime(str(dob_str)[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            today = datetime.now(timezone.utc).date()
            age = (
                today.year
                - birth_date.year
                - ((today.month, today.day) < (birth_date.month, birth_date.day))
            )
            if age < 25:
                return "18-24"
            elif age < 35:
                return "25-34"
            elif age < 50:
                return "35-49"
            elif age < 65:
                return "50-64"
            return "65+"
        except Exception:  # noqa: BLE001
            return "35-49"

    @staticmethod
    def generalize_pincode(pincode: Any) -> str | None:
        """Generalizes 6-digit Indian pincode to 3-digit region prefix."""
        if pincode is None or pd.isna(pincode):
            return None
        s = str(pincode).strip()
        if len(s) >= 3:
            return f"{s[:3]}XXX"
        return "XXX000"

    @staticmethod
    def generalize_ip(ip: Any) -> str | None:
        """Generalizes IPv4 address to /16 subnet."""
        if ip is None or pd.isna(ip):
            return None
        parts = str(ip).strip().split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.X.X"
        return "10.0.X.X"

    @staticmethod
    def redact(value: Any, replacement: str = "[REDACTED]") -> str | None:
        if value is None or pd.isna(value):
            return None
        return replacement

    def mask_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Applies masking transformations across all matching columns in the DataFrame.
        """
        masked_df = df.copy()

        for col, rule in self.rules.items():
            if col not in masked_df.columns:
                continue

            technique = rule.get("technique")
            if technique == "partial_mask":
                if col == "pan":
                    masked_df[col] = masked_df[col].apply(self.mask_pan)
                elif col in ["phone", "account_number"]:
                    keep_last = rule.get("keep_last", 4)
                    masked_df[col] = masked_df[col].apply(
                        lambda v, kl=keep_last: self.mask_phone(v, kl)
                    )
            elif technique == "hmac_token":
                masked_df[col] = masked_df[col].apply(self.hmac_token)
            elif technique == "format_preserving_hash":
                masked_df[col] = masked_df[col].apply(self.mask_email)
            elif technique == "generalisation":
                granularity = rule.get("granularity")
                if granularity == "age_band":
                    masked_df[col] = masked_df[col].apply(self.generalize_dob)
                elif granularity == "prefix_3":
                    masked_df[col] = masked_df[col].apply(self.generalize_pincode)
                elif granularity == "subnet_c":
                    masked_df[col] = masked_df[col].apply(self.generalize_ip)
            elif technique == "redaction":
                replacement = rule.get("replacement", "[REDACTED]")
                masked_df[col] = masked_df[col].apply(
                    lambda v, rep=replacement: self.redact(v, rep)
                )

        masked_df["_masking_key_version"] = self.key_version
        return masked_df
