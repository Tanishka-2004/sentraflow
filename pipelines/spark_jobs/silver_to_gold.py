import os
import sys
import datetime
from decimal import Decimal
import psycopg2
from psycopg2.extras import execute_values
from minio import Minio
# Deferred PySpark imports to allow offline loading without dependencies
# Configs
DB_URL = os.getenv("DATABASE_URL", os.getenv("WAREHOUSE_URL", "postgresql://postgres:postgres@postgres:5432/sentraflow"))
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "localhost:9000").replace("http://", "").replace("https://", "")
S3_BUCKET = os.getenv("S3_BUCKET", "sentraflow-lake")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")

def get_spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder \
        .appName("SilverToGoldDQ") \
        .master("local[*]") \
        .getOrCreate()

def run_silver_to_gold(run_id, is_sandbox=False):
    print(f"Starting Silver -> Gold Transformation & DQ Check. Run ID: {run_id} | Sandbox: {is_sandbox}")
    from pyspark.sql.functions import col
    
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Update status
    cur.execute("UPDATE pipeline_runs SET gold_status = 'running', dq_status = 'running' WHERE run_id = %s", (run_id,))
    conn.commit()
    
    mc = Minio(S3_ENDPOINT, access_key=AWS_ACCESS_KEY, secret_key=AWS_SECRET_ACCESS_KEY, secure=False)
    
    # Create local folder for Parquet download
    os.makedirs("/tmp/spark_runs/silver_parquet", exist_ok=True)
    local_parquet_dir = f"/tmp/spark_runs/silver_parquet/{run_id}"
    os.makedirs(local_parquet_dir, exist_ok=True)
    
    try:
        # 1. Download Silver Parquet files
        silver_prefix = f"silver/{run_id}/" if not is_sandbox else f"silver_sandbox/{run_id}/"
        print(f"Downloading Parquet directory '{silver_prefix}' from MinIO...")
        
        objects = mc.list_objects(S3_BUCKET, prefix=silver_prefix, recursive=True)
        downloaded_any = False
        for obj in objects:
            downloaded_any = True
            local_file = os.path.join(local_parquet_dir, os.path.basename(obj.object_name))
            mc.fget_object(S3_BUCKET, obj.object_name, local_file)
            
        if not downloaded_any:
            raise ValueError(f"No Silver data found in MinIO for path '{silver_prefix}'")
            
        # Start Spark
        spark = get_spark()
        df = spark.read.parquet(local_parquet_dir)
        print(f"Read {df.count()} masked rows from Silver Parquet.")
        
        # -----------------------------------------------------
        # Data Quality (dbt-style) Tests
        # -----------------------------------------------------
        print("Executing Data Quality Test Suite...")
        dq_failures = []
        
        # Test 1: Assert amount is positive
        negative_amounts = df.filter(col("amount") <= 0.0).count()
        status_1 = "pass" if negative_amounts == 0 else "fail"
        details_1 = {"test": "assert_amount_positive", "failing_records": negative_amounts}
        cur.execute("""
            INSERT INTO dq_results (run_id, test_name, model_name, status, details)
            VALUES (%s, 'assert_amount_positive', 'fact_transactions', %s, %s)
        """, (run_id, status_1, psycopg2.extras.Json(details_1)))
        if status_1 == "fail": dq_failures.append("assert_amount_positive")
        
        # Test 2: Assert transaction_id is not null
        null_ids = df.filter(col("transaction_id").isNull()).count()
        status_2 = "pass" if null_ids == 0 else "fail"
        details_2 = {"test": "assert_transaction_id_not_null", "failing_records": null_ids}
        cur.execute("""
            INSERT INTO dq_results (run_id, test_name, model_name, status, details)
            VALUES (%s, 'assert_transaction_id_not_null', 'fact_transactions', %s, %s)
        """, (run_id, status_2, psycopg2.extras.Json(details_2)))
        if status_2 == "fail": dq_failures.append("assert_transaction_id_not_null")
        
        # Write results so they are visible
        conn.commit()
        
        # If any mandatory test fails -> Fail pipeline!
        if len(dq_failures) > 0:
            print(f"CRITICAL: Data quality tests failed: {dq_failures}. Pipeline aborted.")
            cur.execute("""
                UPDATE pipeline_runs 
                SET status = 'failed', gold_status = 'failed', dq_status = 'failed', completed_at = NOW()
                WHERE run_id = %s
            """, (run_id,))
            conn.commit()
            raise ValueError(f"DQ Test Suite failed on pipeline run: {dq_failures}")
            
        cur.execute("UPDATE pipeline_runs SET dq_status = 'success' WHERE run_id = %s", (run_id,))
        conn.commit()
        print("Data Quality tests passed successfully.")
        
        # -----------------------------------------------------
        # Load into Gold Warehouse (Postgres)
        # -----------------------------------------------------
        print("Loading transactions into Gold Warehouse...")
        rows = df.collect()
        
        gold_transactions = []
        for r in rows:
            tx_id = r['transaction_id']
            acc_id = r['account_id']
            amount = r['amount']
            tx_type = r['transaction_type']
            timestamp_str = r['timestamp']
            
            # Format/Parse timestamp
            if isinstance(timestamp_str, str):
                dt = datetime.datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
            else:
                dt = timestamp_str # already datetime or float
                
            date_key = int(dt.strftime("%Y%m%d"))
            
            # Mock risk score calculation (normally runs batch XGBoost model. 
            # In sandbox mode/replays, we assign a low mock risk score)
            risk_score = 0.05
            is_flagged = False
            
            gold_transactions.append((
                tx_id, acc_id, date_key, Decimal(str(amount)), tx_type, risk_score, is_flagged, 'batch', dt
            ))
            
        # Target table (writes to warehouse.fact_transactions in Postgres)
        # If in sandbox, we write to a sandboxed table or schema to keep prod clean
        schema = "warehouse" if not is_sandbox else "public"
        table_name = f"{schema}.fact_transactions"
        
        # Load into DB (Upsert on transaction_id)
        # In Postgres, we use INSERT ON CONFLICT DO UPDATE
        insert_query = f"""
            INSERT INTO {table_name} 
            (transaction_id, account_id, date_key, amount, transaction_type, risk_score, is_flagged, source, created_at)
            VALUES %s
            ON CONFLICT (transaction_id) DO UPDATE SET
                amount = EXCLUDED.amount,
                risk_score = EXCLUDED.risk_score,
                is_flagged = EXCLUDED.is_flagged
        """
        
        execute_values(cur, insert_query, gold_transactions)
        
        # 5. Write Lineage Events
        cur.execute("""
            INSERT INTO lineage_events (run_id, step_name, source_table, source_column, target_table, target_column, event_type)
            VALUES (%s, 'load_gold', 'silver_transactions', NULL, 'fact_transactions', NULL, 'write')
        """, (run_id,))
        
        cur.execute("""
            UPDATE pipeline_runs 
            SET gold_status = 'success', status = 'success', completed_at = NOW()
            WHERE run_id = %s
        """, (run_id,))
        
        conn.commit()
        print("Silver -> Gold pipeline run completed successfully.")
        
    except Exception as e:
        print(f"Pipeline failure: {e}")
        cur.execute("SELECT status FROM pipeline_runs WHERE run_id = %s", (run_id,))
        res = cur.fetchone()
        if res and res[0] == "running":
            cur.execute("""
                UPDATE pipeline_runs 
                SET status = 'failed', gold_status = 'failed', completed_at = NOW()
                WHERE run_id = %s
            """, (run_id,))
            conn.commit()
        raise e
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python silver_to_gold.py <run_id> [--sandbox]")
        sys.exit(1)
    run_id = sys.argv[1]
    sandbox = "--sandbox" in sys.argv
    run_silver_to_gold(run_id, sandbox)
