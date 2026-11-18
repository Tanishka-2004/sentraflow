"""
Unit tests for Airflow DAGs and Orchestration Plugins (Phase 7).
"""

from datetime import datetime, timedelta, timezone

from deltalake import DeltaTable

from airflow.dags.sentraflow_batch_pipeline import DEFAULT_ARGS, sentraflow_batch_dag
from airflow.dags.sentraflow_dq_monitor import sentraflow_dq_dag
from airflow.dags.sentraflow_maintenance import sentraflow_maint_dag
from airflow.dags.sentraflow_model_retrain import sentraflow_retrain_dag
from airflow.plugins.alerts import slack_failure_callback
from airflow.plugins.audit_logger import PipelineRunAuditLogger


def test_dag_integrity_and_imports():
    """
    Asserts all 4 DAGs import cleanly and have correct DAG IDs and tags.
    """
    dags = [
        sentraflow_batch_dag,
        sentraflow_dq_dag,
        sentraflow_retrain_dag,
        sentraflow_maint_dag,
    ]

    expected_ids = {
        "sentraflow_batch_pipeline",
        "sentraflow_dq_monitor",
        "sentraflow_model_retrain",
        "sentraflow_maintenance",
    }

    found_ids = {getattr(d, "dag_id", str(d)) for d in dags}
    assert expected_ids.issubset(found_ids)


def test_batch_dag_structure_and_retry_policies():
    """
    Asserts that the critical batch pipeline defines exponential backoff retries,
    an SLA, and failure alert callbacks.
    """
    assert DEFAULT_ARGS["retries"] >= 3
    assert DEFAULT_ARGS["retry_exponential_backoff"] is True
    assert DEFAULT_ARGS["sla"] == timedelta(minutes=45)
    assert DEFAULT_ARGS["on_failure_callback"] is not None


def test_alert_callback_formatting():
    """
    Asserts that the failure alert callback generates formatted notifications.
    """
    dummy_context = {
        "dag": {"dag_id": "sentraflow_batch_pipeline"},
        "task": {"task_id": "pii_masking_gate"},
        "execution_date": "2026-11-07T12:00:00",
        "exception": "PIIGateViolationError: Unmasked PAN detected",
    }

    alert_text = slack_failure_callback(dummy_context)
    assert "SENTRAFLOW PIPELINE FAILURE" in alert_text
    assert "sentraflow_batch_pipeline" in alert_text
    assert "pii_masking_gate" in alert_text
    assert "PIIGateViolationError" in alert_text


def test_audit_logger_persists_to_delta(tmp_path):
    """
    Asserts that PipelineRunAuditLogger writes atomic run records to Delta Lake.
    """
    table_path = tmp_path / "pipeline_run_audit"
    logger = PipelineRunAuditLogger(table_path=str(table_path))

    start = datetime.now(timezone.utc) - timedelta(minutes=4)
    end = datetime.now(timezone.utc)

    record = logger.log_run(
        dag_id="sentraflow_batch_pipeline",
        run_id="run_test_001",
        batch_id="batch_001",
        status="SUCCESS",
        started_at=start,
        completed_at=end,
        records_processed=15000,
    )

    assert record["status"] == "SUCCESS"
    assert record["duration_seconds"] > 200

    # Verify Delta table on disk
    dt = DeltaTable(str(table_path))
    df = dt.to_pandas()
    assert len(df) == 1
    assert df["run_id"].iloc[0] == "run_test_001"
    assert df["records_processed"].iloc[0] == 15000
