"""
Pipeline Run Audit Logger for SentraFlow.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from deltalake import write_deltalake


class PipelineRunAuditLogger:
    """
    Persists pipeline run audit telemetry to Delta Lake table governance.pipeline_run_audit.
    """

    def __init__(self, table_path: str = "./data/delta/governance/pipeline_run_audit"):
        self.table_path = table_path

    def log_run(
        self,
        dag_id: str,
        run_id: str,
        batch_id: str,
        status: str,
        started_at: datetime,
        completed_at: datetime,
        records_processed: int = 0,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        duration = (completed_at - started_at).total_seconds()
        record = {
            "dag_id": dag_id,
            "run_id": run_id,
            "batch_id": batch_id,
            "status": status,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": round(duration, 2),
            "records_processed": records_processed,
            "error_message": error_message or "None",
        }

        target_dir = Path(self.table_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        write_deltalake(
            self.table_path,
            pd.DataFrame([record]),
            mode="append",
            schema_mode="merge",
        )
        return record
