import os
import sys
import uuid
import datetime
import hashlib
import psycopg2
from minio import Minio
# Deferred PySpark imports to allow standalone utility testing without Spark dependency

# Configs from environment
DB_URL = os.getenv("DATABASE_URL", os.getenv("WAREHOUSE_URL", "postgresql://postgres:postgres@postgres:5432/sentraflow"))
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "localhost:9000").replace("http://", "").replace("https://", "")
S3_BUCKET = os.getenv("S3_BUCKET", "sentraflow-lake")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")

# Spark session setup
def get_spark():
    from pyspark.sql import SparkSession
    return SparkSession.builder \
        .appName("BronzeToSilverPII") \
        .master("local[*]") \
        .getOrCreate()

# Masking UDFs
def hash_val(val):
    if not val: return val
    return hashlib.sha256(str(val).encode('utf-8')).hexdigest()[:16]

def redact_val(val):
    if not val: return val
    s = str(val)
    if len(s) <= 2: return "**"
    return s[0] + "*" * (len(s) - 2) + s[-1]

def tokenize_val(val):
    if not val: return val
    return f"TOK_{hashlib.md5(str(val).encode('utf-8')).hexdigest()[:10]}"


# PII Classification regexes
PII_REGEXES = {
    "email": r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$",
    "ssn": r"^\d{3}-\d{2}-\d{4}$|^\d{9}$",
    "phone": r"^\+?[1-9]\d{1,14}$|^\d{3}-\d{3}-\d{4}$",
    "credit_card": r"^\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}$|^\d{16}$"
}

def scan_column_for_pii(col_name, sample_values):
    """
    Checks if a column contains PII using name matching and sample values regex checks.
    """
    import re
    # Check column name heuristics first
    name_lower = col_name.lower()
    for key in PII_REGEXES.keys():
        if key in name_lower or name_lower == "customer_name" or name_lower == "first_name" or name_lower == "last_name":
            return True, "name_match", key
            
    # Check sample values against regex
    for val in sample_values:
        if not val or not isinstance(val, str):
            continue
        for pii_type, regex in PII_REGEXES.items():
            if re.match(regex, val.strip()):
                return True, "regex_match", pii_type
                
    return False, None, None

def run_pipeline(run_id, is_sandbox=False):
    print(f"Starting Bronze -> Silver Pipeline. Run ID: {run_id} | Sandbox: {is_sandbox}")
    
    from pyspark.sql.functions import col, udf
    from pyspark.sql.types import StringType
    
    hash_udf = udf(hash_val, StringType())
    redact_udf = udf(redact_val, StringType())
    tokenize_udf = udf(tokenize_val, StringType())
    
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # 1. Update pipeline run status
    cur.execute("""
        UPDATE pipeline_runs 
        SET bronze_status = 'running', status = 'running'
        WHERE run_id = %s
    """, (run_id,))
    conn.commit()
    
    # Init MinIO client
    mc = Minio(S3_ENDPOINT, access_key=AWS_ACCESS_KEY, secret_key=AWS_SECRET_KEY, secure=False)
    
    # Create temp files directory
    os.makedirs("/tmp/spark_runs", exist_ok=True)
    local_csv_path = f"/tmp/spark_runs/{run_id}.csv"
    
    try:
        # 2. Download Bronze file
        object_name = "bronze/transactions_historical.csv"
        print(f"Downloading {object_name} from MinIO...")
        mc.fget_object(S3_BUCKET, object_name, local_csv_path)
        
        # Start Spark
        spark = get_spark()
        
        # Load CSV
        df = spark.read.option("header", "true").option("inferSchema", "true").csv(local_csv_path)
        print(f"Read {df.count()} rows from Bronze.")
        
        # 3. PII Detection Gate
        print("Running PII Auto-Detection Gate...")
        
        # Get active PII rules from Postgres
        cur.execute("SELECT column_pattern, rule_type, masking_strategy FROM pii_rules WHERE active = TRUE")
        active_rules = cur.fetchall() # List of (column_pattern, rule_type, masking_strategy)
        
        # Check each column
        columns = df.columns
        for col_name in columns:
            # Sample 100 rows for this column
            samples = [row[0] for row in df.select(col(col_name)).limit(100).collect()]
            
            is_pii, detection_method, pii_type = scan_column_for_pii(col_name, samples)
            
            if is_pii:
                print(f"Detected PII in column: '{col_name}' | Method: {detection_method} | Type: {pii_type}")
                
                # Check if we have an active rule matching this column name pattern
                matching_rule = None
                for pattern, rule_type, strategy in active_rules:
                    clean_pattern = pattern.replace("%", "")
                    if clean_pattern in col_name.lower():
                        matching_rule = (strategy, pattern)
                        break
                        
                if not matching_rule:
                    # FAIL CLOSED!
                    print(f"CRITICAL: Unclassified PII detected in column '{col_name}' with no active masking rule. Failing closed.")
                    cur.execute("""
                        UPDATE pipeline_runs 
                        SET status = 'failed', bronze_status = 'failed', pii_status = 'failed_closed', completed_at = NOW()
                        WHERE run_id = %s
                    """, (run_id,))
                    conn.commit()
                    
                    # Log audit event
                    cur.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
                    admin_id = cur.fetchone()[0]
                    cur.execute("""
                        INSERT INTO audit_log (actor_id, action, resource, target_id, reason, ip_address, user_agent)
                        VALUES (%s, 'PII_VALIDATION_FAILURE', 'pipeline_runs', NULL, %s, '127.0.0.1', 'Airflow Spark Job')
                    """, (admin_id, f"Unclassified PII detected on column '{col_name}'. Promotion blocked (Fail-Closed)."))
                    conn.commit()
                    
                    raise ValueError(f"PII Gate failure: Unclassified PII on column '{col_name}'")
                    
                # Apply Masking strategy
                strategy, pattern = matching_rule
                print(f"Applying masking strategy '{strategy}' for column '{col_name}' matching rule '{pattern}'")
                
                if strategy == "hash":
                    df = df.withColumn(col_name, hash_udf(col(col_name).cast(StringType())))
                elif strategy == "redact":
                    df = df.withColumn(col_name, redact_udf(col(col_name).cast(StringType())))
                elif strategy == "tokenize":
                    df = df.withColumn(col_name, tokenize_udf(col(col_name).cast(StringType())))
                    
                # Write lineage event for masking
                cur.execute("""
                    INSERT INTO lineage_events (run_id, step_name, source_table, source_column, target_table, target_column, event_type)
                    VALUES (%s, 'pii_masking', 'bronze_transactions', %s, 'silver_transactions', %s, 'transform')
                """, (run_id, col_name, col_name))
                
        db_silver_status = "success"
        cur.execute("UPDATE pipeline_runs SET bronze_status = 'success', silver_status = 'success', pii_status = 'success' WHERE run_id = %s", (run_id,))
        conn.commit()
        
        # 4. Save to Silver location
        local_silver_dir = f"/tmp/spark_runs/{run_id}_silver.parquet"
        df.write.mode("overwrite").parquet(local_silver_dir)
        print("PySpark wrote Silver Parquet locally.")
        
        # Upload Silver Parquet to MinIO
        silver_prefix = "silver/" if not is_sandbox else "silver_sandbox/"
        for root, dirs, files in os.walk(local_silver_dir):
            for file in files:
                if file.endswith(".parquet"):
                    local_file_path = os.path.join(root, file)
                    remote_file_name = f"{silver_prefix}{run_id}/{file}"
                    mc.fput_object(S3_BUCKET, remote_file_name, local_file_path)
                    print(f"Uploaded Parquet file to MinIO: {remote_file_name}")
                    
        # Write base table lineage
        cur.execute("""
            INSERT INTO lineage_events (run_id, step_name, source_table, source_column, target_table, target_column, event_type)
            VALUES (%s, 'load_silver', 'bronze_transactions', NULL, 'silver_transactions', NULL, 'write')
        """, (run_id,))
        conn.commit()
        print("Bronze -> Silver pipeline run completed successfully.")
        
    except Exception as e:
        print(f"Pipeline failed: {e}")
        # If not already failed closed by pii
        cur.execute("SELECT status FROM pipeline_runs WHERE run_id = %s", (run_id,))
        row = cur.fetchone()
        current_status = row[0] if row else None
        if current_status == "running":
            cur.execute("""
                UPDATE pipeline_runs 
                SET status = 'failed', bronze_status = 'failed', completed_at = NOW()
                WHERE run_id = %s
            """, (run_id,))
            conn.commit()
        raise e
    finally:
        # Clean up local temporary files
        if os.path.exists(local_csv_path):
            os.remove(local_csv_path)
        cur.close()
        conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bronze_to_silver.py <run_id> [--sandbox]")
        sys.exit(1)
    run_id = sys.argv[1]
    sandbox = "--sandbox" in sys.argv
    run_pipeline(run_id, sandbox)
