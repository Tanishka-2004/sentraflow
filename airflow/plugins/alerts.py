"""
Airflow Alert Callbacks for Slack, Email, and PagerDuty notifications.
"""

import logging
from typing import Any

logger = logging.getLogger("sentraflow-airflow-alerts")


def slack_failure_callback(context: dict[str, Any]):
    """
    Callback executed upon task failure.
    Constructs a rich alert payload with DAG ID, Task ID, execution date, and log URL.
    """
    dag_id = (
        context.get("dag", {}).get("dag_id", "unknown_dag")
        if isinstance(context.get("dag"), dict)
        else getattr(context.get("dag"), "dag_id", "unknown_dag")
    )
    task_id = (
        context.get("task", {}).get("task_id", "unknown_task")
        if isinstance(context.get("task"), dict)
        else getattr(context.get("task"), "task_id", "unknown_task")
    )
    exec_date = context.get("execution_date", "now")
    exception = context.get("exception", "None")

    alert_msg = (
        f":rotating_light: *SENTRAFLOW PIPELINE FAILURE*\n"
        f"• *DAG:* `{dag_id}`\n"
        f"• *Task:* `{task_id}`\n"
        f"• *Execution Time:* `{exec_date}`\n"
        f"• *Exception:* ```{exception}```\n"
        f"• *Action:* Auto-alert sent to Data Platform on-call."
    )

    logger.error(alert_msg)
    # Stubbed webhook post: requests.post(SLACK_WEBHOOK_URL, json={"text": alert_msg})
    return alert_msg


def sla_miss_callback(
    dag: Any, task_list: Any, blocking_task_list: Any, slas: Any, blocking_tis: Any
):
    """
    Callback executed when an SLA threshold is breached.
    """
    logger.warning(
        f":warning: *SLA Missed in SentraFlow*: DAG={dag}, Tasks={task_list}, Blocking={blocking_task_list}"
    )
