"""
PII Scanner for SentraFlow.

Performs dual-method PII detection:
1. Metadata & Classification Registry Rules (YAML-based schema mapping).
2. Content-Based Regular Expression & Heuristic Pattern Scanning on sampled values.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


@dataclass
class ColumnScanResult:
    column_name: str
    detected_type: str | None
    classification: str  # PUBLIC, INTERNAL, CONFIDENTIAL, PII_DIRECT, PII_QUASI
    confidence: float  # 0.0 to 1.0
    match_rate: float
    sample_count: int
    action_required: str  # MASK, GENERALIZE, REDACT, NONE


@dataclass
class ScanReport:
    total_columns_scanned: int
    pii_columns_found: list[str]
    column_results: list[ColumnScanResult]
    has_pii: bool


def _is_unmasked_pan(val: str) -> bool:
    """Matches PAN pattern but excludes already masked formats (e.g. XXXXX1234X)."""
    clean = val.strip().upper()
    if clean.startswith(("XXXXX", "XXX", "[REDACTED")):
        return False
    return bool(re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]$", clean))


def _is_unmasked_email(val: str) -> bool:
    """Matches email pattern but excludes format-preserving hashed emails (h_...)."""
    clean = val.strip()
    if clean.startswith(("h_", "TOK_", "[REDACTED")):
        return False
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", clean))


def _is_unmasked_phone(val: str) -> bool:
    """Matches phone pattern but excludes masked phone numbers with 'X'."""
    clean = val.strip()
    if "X" in clean or clean.startswith("[REDACTED"):
        return False
    return bool(re.match(r"^(\+91)?[6-9]\d{9}$", clean))


def _is_unmasked_aadhaar(val: str) -> bool:
    """Matches 12-digit numbers but excludes redacted tokens."""
    clean = val.strip()
    if "X" in clean or clean.startswith("[REDACTED"):
        return False
    return bool(re.match(r"^\d{12}$", clean))


def _is_unmasked_account(val: str) -> bool:
    """Matches 11-16 digit bank accounts but excludes masked accounts with 'X'."""
    clean = val.strip()
    if "X" in clean or clean.startswith("[REDACTED"):
        return False
    return bool(re.match(r"^\d{11,16}$", clean))


# Evaluator mapping for content inspection
PII_EVALUATORS = {
    "PAN": _is_unmasked_pan,
    "PHONE": _is_unmasked_phone,
    "EMAIL": _is_unmasked_email,
    "AADHAAR_LIKE": _is_unmasked_aadhaar,
    "ACCOUNT_NUMBER": _is_unmasked_account,
    "PINCODE": lambda v: (
        bool(re.match(r"^\d{6}$", v.strip())) and not v.strip().endswith("XXX")
    ),
    "IPV4": lambda v: (
        bool(
            re.match(
                r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$",
                v.strip(),
            )
        )
        and not v.strip().endswith(".X.X")
    ),
}


class PIIScanner:
    """
    Scans DataFrames to detect PII attributes using metadata catalog and content sampling.
    """

    def __init__(self, registry_path: str | None = None):
        if registry_path is None:
            registry_path = str(Path(__file__).parent / "classification_registry.yaml")

        self.registry_path = registry_path
        self.classification_catalog: dict[str, dict[str, Any]] = {}
        self._load_registry()

    def _load_registry(self):
        p = Path(self.registry_path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.classification_catalog = data.get("columns", {})

    def scan_dataframe(self, df: pd.DataFrame, sample_size: int = 500) -> ScanReport:
        """
        Scans all columns in a DataFrame and generates a comprehensive PII report.
        """
        results: list[ColumnScanResult] = []
        pii_columns: list[str] = []

        sample_df = (
            df.sample(min(len(df), sample_size), random_state=42) if len(df) > 0 else df
        )

        for col in df.columns:
            # Metadata rule lookup
            catalog_entry = self.classification_catalog.get(col, {})
            metadata_class = catalog_entry.get("classification", "INTERNAL")

            # Content regex scan on non-null string samples
            series = sample_df[col].dropna().astype(str)
            sample_count = len(series)

            best_match_type: str | None = None
            best_match_rate = 0.0

            if sample_count > 0:
                for pii_name, evaluator in PII_EVALUATORS.items():
                    matches = series.apply(
                        lambda val, ev=evaluator: bool(ev(str(val)))
                    ).sum()
                    match_rate = float(matches) / sample_count
                    if match_rate > best_match_rate and match_rate >= 0.15:
                        best_match_rate = match_rate
                        best_match_type = pii_name

            # Determine final classification & confidence
            is_pii = False
            confidence = 0.0
            action = "NONE"

            if best_match_type:
                # Content explicitly matches PII regex
                confidence = max(best_match_rate, 0.85)
                is_pii = True
                final_class = (
                    "PII_DIRECT"
                    if best_match_type
                    in ["PAN", "AADHAAR_LIKE", "PHONE", "EMAIL", "ACCOUNT_NUMBER"]
                    else "PII_QUASI"
                )
            elif metadata_class in ["PII_DIRECT", "PII_QUASI"]:
                # Metadata tags as PII
                confidence = 0.90
                is_pii = True
                final_class = metadata_class
            else:
                final_class = metadata_class
                confidence = 0.10

            if is_pii:
                pii_columns.append(col)
                if final_class == "PII_DIRECT":
                    action = "MASK"
                elif final_class == "PII_QUASI":
                    action = "GENERALIZE"

            results.append(
                ColumnScanResult(
                    column_name=col,
                    detected_type=best_match_type or catalog_entry.get("category"),
                    classification=final_class,
                    confidence=round(confidence, 2),
                    match_rate=round(best_match_rate, 2),
                    sample_count=sample_count,
                    action_required=action,
                )
            )

        return ScanReport(
            total_columns_scanned=len(df.columns),
            pii_columns_found=pii_columns,
            column_results=results,
            has_pii=len(pii_columns) > 0,
        )
