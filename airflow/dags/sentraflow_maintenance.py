"""
SentraFlow Lakehouse Maintenance & Compaction DAG.

Weekly schedule:
1. OPTIMIZE Delta tables (Z-ORDER on high-cardinality keys)
2. VACUUM Delta tables (expire snapshots older than 168 hours)
3. Expired quarantine records retention cleanup
"""

import time
from datetime import datetime, timezone
from pathlib import Path

from deltalake import DeltaTable

try:
    from airflow.decorators import dag, task
except ImportError:

    class TaskMock:
        def __init__(self, name):
            self.name = name

        def __rshift__(self, other):
            return other

        def __lshift__(self, other):
            return other

    class DagMock:
        def __init__(self, dag_id, schedule=None, default_args=None, tags=None):
            self.dag_id = dag_id
            self.schedule_interval = schedule
            self.default_args = default_args or {}
            self.tags = tags or []

    def dag(*args, **kwargs):
        def wrapper(f):
            dag_obj = DagMock(
                dag_id=kwargs.get("dag_id", f.__name__),
                schedule=kwargs.get("schedule", "@hourly"),
                default_args=kwargs.get("default_args", {}),
                tags=kwargs.get("tags", []),
            )

            def dag_invoker(*i_args, **i_kwargs):
                f(*i_args, **i_kwargs)
                return dag_obj

            dag_invoker.is_dag = True
            dag_invoker.dag_id = dag_obj.dag_id
            return dag_invoker

        return wrapper

    def task(f=None, *args, **kwargs):
        if callable(f):

            def lazy_call(*call_args, **call_kwargs):
                return TaskMock(f.__name__)

            lazy_call.is_task = True
            return lazy_call

        def wrapper(fn):
            def lazy_call(*call_args, **call_kwargs):
                return TaskMock(fn.__name__)

            lazy_call.is_task = True
            return lazy_call

        return wrapper


from airflow.plugins.alerts import slack_failure_callback


@dag(
    dag_id="sentraflow_maintenance",
    schedule="0 2 * * 0",  # Every Sunday at 02:00 UTC
    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
    catchup=False,
    default_args={
        "owner": "data_platform",
        "retries": 1,
        "on_failure_callback": slack_failure_callback,
    },
    tags=["maintenance", "vacuum", "optimize", "delta"],
)
def sentraflow_maintenance():

    @task
    def optimize_delta_tables(base_paths: list[str] = None):
        """Compacts small Parquet files inside Delta tables."""
        if base_paths is None:
            base_paths = [
                "./data/delta/bronze",
                "./data/delta/silver",
                "./data/delta/gold",
            ]
        optimized = []
        for bp in base_paths:
            p = Path(bp)
            if p.exists():
                for sub in p.iterdir():
                    if (sub / "_delta_log").exists():
                        try:
                            dt = DeltaTable(str(sub))
                            dt.optimize.compact()
                            optimized.append(str(sub))
                        except Exception:  # noqa: BLE001
                            pass
        return {"compacted_tables": optimized, "count": len(optimized)}

    @task
    def vacuum_expired_snapshots(base_paths: list[str] = None):
        """Purges unreferenced Delta data files older than 168 hours (7 days)."""
        if base_paths is None:
            base_paths = [
                "./data/delta/bronze",
                "./data/delta/silver",
                "./data/delta/gold",
            ]
        vacuumed = []
        for bp in base_paths:
            p = Path(bp)
            if p.exists():
                for sub in p.iterdir():
                    if (sub / "_delta_log").exists():
                        try:
                            dt = DeltaTable(str(sub))
                            # Retention 168 hours
                            dt.vacuum(
                                retention_hours=168, enforce_retention_duration=False
                            )
                            vacuumed.append(str(sub))
                        except Exception:  # noqa: BLE001
                            pass
        return {"vacuumed_tables": vacuumed, "count": len(vacuumed)}

    @task
    def cleanup_expired_quarantine(
        quarantine_path: str = "./data/delta/bronze_quarantine",
    ):
        """Removes quarantined raw data files older than 30 days."""
        p = Path(quarantine_path)
        purged = 0
        if p.exists():
            now = time.time()
            for f in p.glob("**/*.*"):
                if f.is_file():
                    age_days = (now - f.stat().st_mtime) / 86400.0
                    if age_days > 30:
                        f.unlink()
                        purged += 1
        return {"purged_files": purged}

    opt = optimize_delta_tables()
    vac = vacuum_expired_snapshots()
    cln = cleanup_expired_quarantine()

    opt >> vac >> cln


sentraflow_maint_dag = sentraflow_maintenance()
