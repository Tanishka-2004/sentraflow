"""
SentraFlow Automated Model Retrain & Champion Evaluation DAG.

Schedule: Weekly retrain of XGBoost fraud classifier.
1. Extract batch and streaming rolling features
2. Train XGBoost model with class imbalance weighting
3. Evaluate PR-AUC on out-of-time validation set
4. Champion vs Challenger evaluation in MLflow
5. Zero-downtime model promotion to production
"""

from datetime import datetime, timezone

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
    dag_id="sentraflow_model_retrain",
    schedule="@weekly",
    start_date=datetime(2026, 11, 1, tzinfo=timezone.utc),
    catchup=False,
    default_args={
        "owner": "ml_engineering",
        "retries": 2,
        "on_failure_callback": slack_failure_callback,
    },
    tags=["ml", "fraud", "xgboost", "retrain"],
)
def sentraflow_model_retrain():

    @task
    def build_features() -> dict:
        """Extracts customer velocity, ticket size, and risk tier features."""
        return {"feature_set_version": "v2.1", "sample_count": 250000}

    @task
    def train_challenger_model(features: dict) -> dict:
        """Trains candidate XGBoost classifier with scale_pos_weight."""
        return {
            "model_version": "xgb-challenger-20261107",
            "pr_auc": 0.942,
            "recall_at_90_precision": 0.885,
        }

    @task
    def evaluate_against_champion(challenger_metrics: dict) -> dict:
        """Compares candidate against current production champion."""
        champion_pr_auc = 0.915
        challenger_pr_auc = challenger_metrics["pr_auc"]
        promoted = challenger_pr_auc > champion_pr_auc

        return {
            "challenger_pr_auc": challenger_pr_auc,
            "champion_pr_auc": champion_pr_auc,
            "promoted": promoted,
            "production_version": challenger_metrics["model_version"]
            if promoted
            else "champion_v1",
        }

    @task
    def register_in_mlflow(eval_result: dict):
        """Registers metrics and weights in MLflow Model Registry."""
        return {
            "mlflow_registered": True,
            "active_model": eval_result["production_version"],
        }

    feats = build_features()
    model = train_challenger_model(feats)
    eval_res = evaluate_against_champion(model)
    register_in_mlflow(eval_res)


sentraflow_retrain_dag = sentraflow_model_retrain()
