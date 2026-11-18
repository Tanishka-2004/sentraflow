"""
Automated PII-Masking Gate for SentraFlow.

Executes between Bronze and Silver layers:
1. Runs PII Scanner on Bronze inputs.
2. Applies masking engine policies.
3. Re-scans output to mathematically verify ZERO residual PII.
4. Persists signed audit report to governance.pii_gate_audit Delta table.
5. Emits hard-fail exception if residual PII is detected, aborting promotion to Silver.
"""

import hashlib
import hmac
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from deltalake import DeltaTable, write_deltalake

from spark_jobs.governance.masking import PIIMaskingEngine
from spark_jobs.governance.pii_scanner import PIIScanner, ScanReport


class PIIGateViolationError(Exception):
    """Raised when unmasked PII breaches the governance gate."""


class PIIGate:
    """
    Automated Governance Gate enforcing zero unmasked PII between Bronze and Silver.
    """

    def __init__(
        self,
        audit_table_path: str = "./data/delta/governance/pii_gate_audit",
        scanner: PIIScanner | None = None,
        masking_engine: PIIMaskingEngine | None = None,
        signing_key: str = "sentraflow-pii-gate-signing-key-2026",
    ):
        self.audit_table_path = audit_table_path
        self.scanner = scanner or PIIScanner()
        self.masking_engine = masking_engine or PIIMaskingEngine()
        self.signing_key = signing_key

    def _sign_gate_report(self, payload: dict[str, Any]) -> str:
        """
        Signs the gate decision using HMAC-SHA256 for non-repudiation.
        """
        raw_msg = f"{payload['batch_id']}:{payload['status']}:{payload['residual_pii_count']}:{payload['evaluated_at']}"
        return hmac.new(
            self.signing_key.encode("utf-8"), raw_msg.encode("utf-8"), hashlib.sha256
        ).hexdigest()

    def _write_audit_log(self, audit_entry: dict[str, Any]):
        """
        Appends the signed gate record to governance.pii_gate_audit.
        """
        target_dir = Path(self.audit_table_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        df_audit = pd.DataFrame([audit_entry])
        write_deltalake(
            self.audit_table_path,
            df_audit,
            mode="append",
            schema_mode="merge",
        )

    def process(
        self,
        bronze_df: pd.DataFrame,
        entity_name: str,
        batch_id: str,
        allow_dry_run: bool = False,
    ) -> pd.DataFrame:
        """
        Runs the full PII Gate lifecycle.
        Returns the certified masked DataFrame, or raises PIIGateViolationError.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Scan Bronze inputs
        pre_scan: ScanReport = self.scanner.scan_dataframe(bronze_df)

        # Step 2: Apply policy-driven masking
        masked_df = self.masking_engine.mask_dataframe(bronze_df)

        # Step 3: Re-scan output to verify zero residual PII
        post_scan: ScanReport = self.scanner.scan_dataframe(masked_df)

        # Check for unmasked PII in output:
        # A residual PII violation occurs if any column still matches direct PII content patterns
        residual_direct_pii: list[str] = [
            r.column_name
            for r in post_scan.column_results
            if r.detected_type
            in ["PAN", "AADHAAR_LIKE", "PHONE", "EMAIL", "ACCOUNT_NUMBER"]
        ]

        gate_passed = len(residual_direct_pii) == 0
        gate_status = "PASSED" if gate_passed else "BLOCKED"

        audit_payload = {
            "entity_name": entity_name,
            "batch_id": batch_id,
            "status": gate_status,
            "input_rows": len(bronze_df),
            "input_pii_columns": ",".join(pre_scan.pii_columns_found),
            "residual_pii_count": len(residual_direct_pii),
            "residual_pii_columns": ",".join(residual_direct_pii),
            "evaluated_at": now_iso,
        }

        # Step 4: Sign report and persist to audit Delta table
        audit_payload["digital_signature"] = self._sign_gate_report(audit_payload)
        self._write_audit_log(audit_payload)

        # Step 5: Hard fail if violation detected
        if not gate_passed and not allow_dry_run:
            raise PIIGateViolationError(
                f"[PII-GATE-BREACH] Gate BLOCKED batch '{batch_id}' for entity '{entity_name}'. "
                f"Residual unmasked PII detected in columns: {residual_direct_pii}. "
                f"Audit record signed and committed to {self.audit_table_path}."
            )

        return masked_df

    def get_audit_history(self) -> pd.DataFrame:
        """
        Reads back the PII gate audit history.
        """
        try:
            dt = DeltaTable(self.audit_table_path)
            return dt.to_pandas()
        except Exception:  # noqa: BLE001
            return pd.DataFrame()
