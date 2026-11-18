from datetime import datetime, timedelta
import uuid
import psycopg2
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.models import Variable
import os

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/sentraflow")

default_args = {
    'owner': 'DataEngineers',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=2)
}

def register_run_start(**context):
    """
    Generates run metadata, versions, and registers the run in public.pipeline_runs.
    Passes the run_id to downstream tasks using XCom.
    """
    dag_run_id = context['run_id']
    run_id = f"RUN_{int(datetime.utcnow().timestamp())}_{str(uuid.uuid4())[:8]}"
    
    # Push generated run_id to xcom
    context['ti'].xcom_push(key='run_id', value=run_id)
    
    print(f"Registering pipeline run start: {run_id}")
    
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    try:
        # Create pipeline run checkpoint in db
        cur.execute("""
            INSERT INTO pipeline_runs (
                run_id, pipeline_version, code_version, schema_version, model_version, input_snapshot, started_at, status,
                bronze_status, silver_status, pii_status, dq_status, gold_status
            ) VALUES (
                %s, 'v2.4.1', 'git-main-bf47c2', 'v7', 'fraud-xgboost-v1', 's3://sentraflow-lake/bronze/transactions_historical.csv', NOW(), 'running',
                'pending', 'pending', 'pending', 'pending', 'pending'
            )
        """, (run_id,))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
        raise e
    finally:
        cur.close()
        conn.close()

with DAG(
    'sentraflow_medallion_pipeline',
    default_args=default_args,
    description='SentraFlow Governed Medallion Data Lakehouse Ingestion Pipeline',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=['sentraflow', 'lakehouse']
) as dag:

    # 1. Register run in DB
    init_run = PythonOperator(
        task_id='init_run_telemetry',
        python_callable=register_run_start,
        provide_context=True
    )

    # 2. Spark Job: Bronze to Silver (PII Classification & Masking)
    # Reads run_id from XCom and passes as parameter
    spark_bronze_to_silver = BashOperator(
        task_id='spark_bronze_to_silver',
        bash_command='python /opt/airflow/spark_jobs/bronze_to_silver.py {{ ti.xcom_pull(task_ids="init_run_telemetry", key="run_id") }}'
    )

    # 3. Spark Job: Silver to Gold (Data Quality tests & Loading)
    spark_silver_to_gold = BashOperator(
        task_id='spark_silver_to_gold',
        bash_command='python /opt/airflow/spark_jobs/silver_to_gold.py {{ ti.xcom_pull(task_ids="init_run_telemetry", key="run_id") }}'
    )

    init_run >> spark_bronze_to_silver >> spark_silver_to_gold
