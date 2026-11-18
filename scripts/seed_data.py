import os
import sys
import csv
import json
import random
import hashlib
import datetime
from decimal import Decimal
import psycopg2
from psycopg2.extras import execute_values
from minio import Minio
from io import BytesIO

# Password hashing with fallback
try:
    import bcrypt
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
except ImportError:
    print("Warning: 'bcrypt' not found. Falling back to SHA-256 for seeding.")
    def hash_password(password: str) -> str:
        # Simulate a bcrypt-like hash format (or just SHA256)
        salt = "salt1234"
        hashed = hashlib.sha256((password + salt).encode('utf-8')).hexdigest()
        return f"$sha256${salt}${hashed}"

# Configs (read from env or fallback to localhost defaults)
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sentraflow")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "localhost:9000").replace("http://", "").replace("https://", "")
S3_BUCKET = os.getenv("S3_BUCKET", "sentraflow-lake")
AWS_ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")

def get_db_connection():
    return psycopg2.connect(DB_URL)

def reset_database(conn):
    print("Performing administrative database truncate cascade...")
    cur = conn.cursor()
    cur.execute("ALTER TABLE audit_log DISABLE TRIGGER ALL")
    cur.execute("TRUNCATE pipeline_runs, alerts, pii_rules, users, catalog_columns, catalog_datasets, model_drift_metrics, model_registry, audit_log RESTART IDENTITY CASCADE")
    cur.execute("ALTER TABLE audit_log ENABLE TRIGGER ALL")
    conn.commit()
    cur.close()

def seed_users(conn):
    print("Seeding users...")
    cur = conn.cursor()
    
    users = [
        ('admin@sentraflow.com', hash_password('admin'), 'admin'),
        ('analyst@sentraflow.com', hash_password('analyst'), 'analyst'),
        ('auditor@sentraflow.com', hash_password('auditor'), 'auditor')
    ]
    
    # Already truncated in reset_database
    cur.executemany(
        "INSERT INTO users (email, password_hash, role) VALUES (%s, %s, %s)",
        users
    )
    conn.commit()
    print("Users seeded successfully.")

def seed_model_registry(conn):
    print("Seeding model registry...")
    cur = conn.cursor()
    
    
    cur.execute("""
        INSERT INTO model_registry (
            model_version, training_dataset_version, feature_version, precision, recall, f1, roc_auc, status, approved_by, approved_at, deployment_status, drift_status
        ) VALUES (
            'fraud-xgboost-v1', 'transactions_historical_v1', 'feature-set-v1', 0.92, 0.88, 0.90, 0.94, 'production', 'ML Admin', NOW(), 'active', 'stable'
        )
    """)
    conn.commit()
    print("Model registry seeded.")

def seed_pii_rules(conn):
    print("Seeding PII governance rules...")
    cur = conn.cursor()
    
    
    # Get admin user ID
    cur.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
    admin_id = cur.fetchone()[0]
    
    rules = [
        ('%email%', 'regex', 'hash', admin_id),
        ('%phone%', 'regex', 'redact', admin_id),
        ('%ssn%', 'regex', 'redact', admin_id),
        ('%first_name%', 'classifier', 'redact', admin_id),
        ('%last_name%', 'classifier', 'redact', admin_id),
        ('%name%', 'classifier', 'redact', admin_id)
    ]
    
    cur.executemany(
        "INSERT INTO pii_rules (column_pattern, rule_type, masking_strategy, created_by) VALUES (%s, %s, %s, %s)",
        rules
    )
    conn.commit()
    print("PII governance rules seeded.")

def seed_data_catalog(conn):
    print("Seeding data catalog...")
    cur = conn.cursor()
    
    
    # Datasets
    datasets = [
        ('raw_transactions', 'Immutable CSV transactions ingested from core-banking/ERP.', 'Data Platform Team', 's3://sentraflow-lake/bronze/'),
        ('silver_transactions', 'Cleaned, schema-enforced, and PII-masked transaction dataset.', 'Data Platform Team', 's3://sentraflow-lake/silver/'),
        ('dim_customer', 'Customer dimension containing SCD Type 2 history.', 'Risk Engineering', 'warehouse.dim_customer'),
        ('dim_account', 'Account dimension detailing status and type.', 'Risk Engineering', 'warehouse.dim_account'),
        ('fact_transactions', 'Scored and validated fact table for transaction details.', 'Risk Engineering', 'warehouse.fact_transactions')
    ]
    
    dataset_ids = {}
    for name, description, owner, storage_path in datasets:
        cur.execute(
            "INSERT INTO catalog_datasets (name, description, owner, storage_path) VALUES (%s, %s, %s, %s) RETURNING id, name",
            (name, description, owner, storage_path)
        )
        ds_id, ds_name = cur.fetchone()
        dataset_ids[ds_name] = ds_id
    
    # Columns mapping
    columns = [
        # raw_transactions (Bronze)
        (dataset_ids['raw_transactions'], 'transaction_id', 'VARCHAR', 'Unique transaction identifier', False, 'low', 'none'),
        (dataset_ids['raw_transactions'], 'account_id', 'VARCHAR', 'Source account identifier', False, 'low', 'none'),
        (dataset_ids['raw_transactions'], 'amount', 'NUMERIC', 'Transaction value in USD', False, 'low', 'none'),
        (dataset_ids['raw_transactions'], 'transaction_type', 'VARCHAR', 'Type (TRANSFER, DEPOSIT, etc.)', False, 'low', 'none'),
        (dataset_ids['raw_transactions'], 'customer_name', 'VARCHAR', 'Full customer name (raw PII)', True, 'high', 'redact'),
        (dataset_ids['raw_transactions'], 'email', 'VARCHAR', 'Customer email address', True, 'high', 'hash'),
        (dataset_ids['raw_transactions'], 'phone', 'VARCHAR', 'Customer phone number', True, 'high', 'redact'),
        (dataset_ids['raw_transactions'], 'timestamp', 'TIMESTAMP', 'Ingestion timestamp', False, 'low', 'none'),
        
        # silver_transactions (Silver)
        (dataset_ids['silver_transactions'], 'transaction_id', 'VARCHAR', 'Unique transaction identifier', False, 'low', 'none'),
        (dataset_ids['silver_transactions'], 'account_id', 'VARCHAR', 'Source account identifier', False, 'low', 'none'),
        (dataset_ids['silver_transactions'], 'amount', 'NUMERIC', 'Cleaned transaction value', False, 'low', 'none'),
        (dataset_ids['silver_transactions'], 'transaction_type', 'VARCHAR', 'Cleaned type', False, 'low', 'none'),
        (dataset_ids['silver_transactions'], 'customer_name', 'VARCHAR', 'Redacted customer name', True, 'medium', 'redact'),
        (dataset_ids['silver_transactions'], 'email', 'VARCHAR', 'Hashed email address', True, 'medium', 'hash'),
        (dataset_ids['silver_transactions'], 'phone', 'VARCHAR', 'Redacted phone number', True, 'medium', 'redact'),
        (dataset_ids['silver_transactions'], 'timestamp', 'TIMESTAMP', 'Standardized timestamp', False, 'low', 'none'),
        
        # dim_customer (Gold)
        (dataset_ids['dim_customer'], 'customer_key', 'SERIAL', 'Surrogate key', False, 'low', 'none'),
        (dataset_ids['dim_customer'], 'customer_id', 'VARCHAR', 'Natural customer key', False, 'low', 'none'),
        (dataset_ids['dim_customer'], 'first_name', 'VARCHAR', 'Redacted first name', True, 'medium', 'redact'),
        (dataset_ids['dim_customer'], 'last_name', 'VARCHAR', 'Redacted last name', True, 'medium', 'redact'),
        (dataset_ids['dim_customer'], 'email', 'VARCHAR', 'Hashed email', True, 'medium', 'hash'),
        (dataset_ids['dim_customer'], 'phone', 'VARCHAR', 'Redacted phone', True, 'medium', 'redact'),
        (dataset_ids['dim_customer'], 'scd_effective_from', 'TIMESTAMP', 'SCD Start Time', False, 'low', 'none'),
        (dataset_ids['dim_customer'], 'scd_effective_to', 'TIMESTAMP', 'SCD End Time', False, 'low', 'none'),
        (dataset_ids['dim_customer'], 'is_current', 'BOOLEAN', 'SCD Current Record indicator', False, 'low', 'none'),
        
        # fact_transactions (Gold)
        (dataset_ids['fact_transactions'], 'transaction_id', 'VARCHAR', 'Natural transaction key', False, 'low', 'none'),
        (dataset_ids['fact_transactions'], 'account_id', 'VARCHAR', 'Account key', False, 'low', 'none'),
        (dataset_ids['fact_transactions'], 'date_key', 'INT', 'Date key surrogate link', False, 'low', 'none'),
        (dataset_ids['fact_transactions'], 'amount', 'NUMERIC', 'Transaction amount', False, 'low', 'none'),
        (dataset_ids['fact_transactions'], 'transaction_type', 'VARCHAR', 'Type of transaction', False, 'low', 'none'),
        (dataset_ids['fact_transactions'], 'risk_score', 'FLOAT', 'ML-generated fraud risk score', False, 'low', 'none'),
        (dataset_ids['fact_transactions'], 'is_flagged', 'BOOLEAN', 'Indicates if transaction is flagged for fraud review', False, 'low', 'none'),
        (dataset_ids['fact_transactions'], 'source', 'VARCHAR', 'Ingestion source (batch/stream)', False, 'low', 'none')
    ]
    
    cur.executemany(
        "INSERT INTO catalog_columns (dataset_id, name, data_type, description, is_pii, sensitivity, masking_strategy) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        columns
    )
    conn.commit()
    print("Data catalog seeded.")

def seed_warehouse_marts(conn):
    print("Seeding Gold warehouse marts...")
    cur = conn.cursor()
    
    # Clean up warehouse tables
    cur.execute("TRUNCATE warehouse.fact_transactions CASCADE")
    cur.execute("TRUNCATE warehouse.dim_account CASCADE")
    cur.execute("TRUNCATE warehouse.dim_customer CASCADE")
    cur.execute("TRUNCATE warehouse.dim_time CASCADE")
    
    # 1. Seed dim_time
    print("Generating Time Dimension...")
    start_date = datetime.date(2026, 7, 1)
    end_date = datetime.date(2026, 8, 31)
    current_date = start_date
    time_records = []
    
    while current_date <= end_date:
        date_key = int(current_date.strftime("%Y%m%d"))
        time_records.append((
            date_key,
            current_date,
            current_date.weekday() + 1,
            current_date.month,
            (current_date.month - 1) // 3 + 1,
            current_date.year
        ))
        current_date += datetime.timedelta(days=1)
        
    execute_values(
        cur,
        "INSERT INTO warehouse.dim_time (date_key, date, day_of_week, month, quarter, year) VALUES %s",
        time_records
    )
    
    # 2. Seed dim_customer (Masked details)
    print("Generating Customer Dimension...")
    customer_ids = [f"CUST_{i:04d}" for i in range(1, 51)]
    first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Elizabeth", "William", "Linda", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
    
    customer_records = []
    for cid in customer_ids:
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        email = f"{fn.lower()}.{ln.lower()}@example.com"
        phone = f"+1-555-{random.randint(100, 999):03d}-{random.randint(1000, 9999):04d}"
        addr = f"{random.randint(100, 9999)} Main St, City_{random.randint(1, 10)}"
        
        # Apply Silver/Gold masking
        masked_fn = fn[0] + "*" * (len(fn) - 1)
        masked_ln = ln[0] + "*" * (len(ln) - 1)
        hashed_email = hashlib.sha256(email.encode()).hexdigest()[:16]
        masked_phone = phone[:4] + "***-***-" + phone[-4:]
        
        customer_records.append((
            cid,
            masked_fn,
            masked_ln,
            hashed_email,
            masked_phone,
            addr,
            datetime.datetime(2026, 7, 1),
            None,
            True
        ))
        
    execute_values(
        cur,
        "INSERT INTO warehouse.dim_customer (customer_id, first_name, last_name, email, phone, address, scd_effective_from, scd_effective_to, is_current) VALUES %s",
        customer_records
    )
    
    # 3. Seed dim_account
    print("Generating Account Dimension...")
    account_records = []
    account_ids = []
    account_types = ["SAVINGS", "CHECKING", "CREDIT"]
    for i, cid in enumerate(customer_ids):
        # 1 or 2 accounts per customer
        for j in range(random.randint(1, 2)):
            acc_id = f"ACC_{i:04d}_{j}"
            account_ids.append(acc_id)
            account_records.append((
                acc_id,
                cid,
                random.choice(account_types),
                datetime.date(2025, random.randint(1, 12), random.randint(1, 28))
            ))
            
    execute_values(
        cur,
        "INSERT INTO warehouse.dim_account (account_id, customer_id, account_type, opened_date) VALUES %s",
        account_records
    )
    
    # 4. Seed fact_transactions (5000 transactions)
    print("Generating 5000 Transaction records...")
    transaction_records = []
    tx_types = ["TRANSFER", "CASH_OUT", "PAYMENT", "CASH_IN"]
    
    for i in range(1, 5001):
        tx_id = f"TX_{i:06d}"
        acc_id = random.choice(account_ids)
        # Random date in July/August 2026
        tx_date = start_date + datetime.timedelta(days=random.randint(0, 50))
        date_key = int(tx_date.strftime("%Y%m%d"))
        
        amount = Decimal(str(round(random.lognormvariate(5, 1.5), 2)))
        # Keep amount within bounds
        if amount < 1:
            amount = Decimal("5.00")
        elif amount > 50000:
            amount = Decimal("45200.00")
            
        tx_type = random.choice(tx_types)
        
        # Fraud logic simulation
        is_fraud = False
        risk_score = float(random.uniform(0.0, 0.29))
        
        # 0.2% fraud rate
        if random.random() < 0.002:
            is_fraud = True
            risk_score = float(random.uniform(0.75, 0.99))
        elif amount > 10000 and random.random() < 0.15:
            # High amount -> higher risk
            risk_score = float(random.uniform(0.35, 0.74))
            
        is_flagged = risk_score >= 0.30
        source = 'batch' if random.random() < 0.85 else 'stream'
        
        transaction_records.append((
            tx_id,
            acc_id,
            date_key,
            amount,
            tx_type,
            risk_score,
            is_flagged,
            source,
            datetime.datetime.combine(tx_date, datetime.time(random.randint(0, 23), random.randint(0, 59)))
        ))
        
    execute_values(
        cur,
        """INSERT INTO warehouse.fact_transactions 
           (transaction_id, account_id, date_key, amount, transaction_type, risk_score, is_flagged, source, created_at) 
           VALUES %s""",
        transaction_records
    )
    
    # 5. Populate alerts for flagged transactions
    print("Creating alerts for flagged transactions...")
    cur.execute("""
        INSERT INTO alerts (transaction_id, risk_score, risk_level, status)
        SELECT 
            transaction_id, 
            risk_score,
            CASE 
                WHEN risk_score >= 0.90 THEN 'CRITICAL'
                WHEN risk_score >= 0.70 THEN 'HIGH'
                ELSE 'MEDIUM'
            END as risk_level,
            'open' as status
        FROM warehouse.fact_transactions
        WHERE is_flagged = TRUE
    """)
    
    # 6. Seed lineage events for batch pipeline runs
    print("Seeding lineage events...")
    lineage_events = [
        # Bronze -> Silver column lineage
        ('RUN_MOCK_101', 'spark_bronze_silver', 'raw_transactions', 'transaction_id', 'silver_transactions', 'transaction_id', 'transform'),
        ('RUN_MOCK_101', 'spark_bronze_silver', 'raw_transactions', 'account_id', 'silver_transactions', 'account_id', 'transform'),
        ('RUN_MOCK_101', 'spark_bronze_silver', 'raw_transactions', 'amount', 'silver_transactions', 'amount', 'transform'),
        ('RUN_MOCK_101', 'spark_bronze_silver', 'raw_transactions', 'transaction_type', 'silver_transactions', 'transaction_type', 'transform'),
        ('RUN_MOCK_101', 'spark_bronze_silver', 'raw_transactions', 'customer_name', 'silver_transactions', 'customer_name', 'transform'),
        ('RUN_MOCK_101', 'spark_bronze_silver', 'raw_transactions', 'email', 'silver_transactions', 'email', 'transform'),
        ('RUN_MOCK_101', 'spark_bronze_silver', 'raw_transactions', 'phone', 'silver_transactions', 'phone', 'transform'),
        ('RUN_MOCK_101', 'spark_bronze_silver', 'raw_transactions', 'timestamp', 'silver_transactions', 'timestamp', 'transform'),
        
        # Silver -> Gold Warehouse lineage
        ('RUN_MOCK_102', 'dbt_silver_gold', 'silver_transactions', 'transaction_id', 'fact_transactions', 'transaction_id', 'write'),
        ('RUN_MOCK_102', 'dbt_silver_gold', 'silver_transactions', 'account_id', 'fact_transactions', 'account_id', 'write'),
        ('RUN_MOCK_102', 'dbt_silver_gold', 'silver_transactions', 'amount', 'fact_transactions', 'amount', 'write'),
        ('RUN_MOCK_102', 'dbt_silver_gold', 'silver_transactions', 'transaction_type', 'fact_transactions', 'transaction_type', 'write'),
        
        # Customer lineage
        ('RUN_MOCK_102', 'dbt_silver_gold', 'silver_transactions', 'customer_name', 'dim_customer', 'first_name', 'transform'),
        ('RUN_MOCK_102', 'dbt_silver_gold', 'silver_transactions', 'customer_name', 'dim_customer', 'last_name', 'transform'),
        ('RUN_MOCK_102', 'dbt_silver_gold', 'silver_transactions', 'email', 'dim_customer', 'email', 'transform'),
        ('RUN_MOCK_102', 'dbt_silver_gold', 'silver_transactions', 'phone', 'dim_customer', 'phone', 'transform')
    ]
    cur.executemany(
        """INSERT INTO lineage_events 
           (run_id, step_name, source_table, source_column, target_table, target_column, event_type) 
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        lineage_events
    )
    
    conn.commit()
    print("Warehouse and lineage seeded.")

def upload_raw_to_minio():
    print("Uploading raw historical transaction CSV to MinIO...")
    # Generate raw CSV file representing ERP/Core Bank extract
    import io
    csv_buffer = io.StringIO()
    writer = csv.writer(csv_buffer)
    
    # CSV Header
    writer.writerow(['transaction_id', 'account_id', 'amount', 'transaction_type', 'customer_name', 'email', 'phone', 'timestamp'])
    
    # Generate 500 rows of mock raw csv data
    first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Elizabeth", "William", "Linda"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
    tx_types = ["TRANSFER", "CASH_OUT", "PAYMENT", "CASH_IN"]
    
    for i in range(1, 501):
        tx_id = f"TX_RAW_{i:04d}"
        acc_id = f"ACC_{random.randint(1, 50):04d}_{random.randint(0, 1)}"
        amount = round(random.lognormvariate(4.5, 1.2), 2)
        tx_type = random.choice(tx_types)
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        name = f"{fn} {ln}"
        email = f"{fn.lower()}.{ln.lower()}@example.com"
        phone = f"+1-555-{random.randint(100, 999):03d}-{random.randint(1000, 9999):04d}"
        timestamp = (datetime.datetime.now() - datetime.timedelta(days=random.randint(0, 5))).strftime("%Y-%m-%d %H:%M:%S")
        
        writer.writerow([tx_id, acc_id, amount, tx_type, name, email, phone, timestamp])
        
    csv_bytes = csv_buffer.getvalue().encode('utf-8')
        
    # Connect and upload
    try:
        mc = Minio(
            S3_ENDPOINT,
            access_key=AWS_ACCESS_KEY,
            secret_key=AWS_SECRET_KEY,
            secure=False
        )
        
        # Verify bucket exists
        if not mc.bucket_exists(S3_BUCKET):
            mc.make_bucket(S3_BUCKET)
            print(f"Created MinIO bucket '{S3_BUCKET}'")
            
        mc.put_object(
            S3_BUCKET,
            "bronze/transactions_historical.csv",
            BytesIO(csv_bytes),
            length=len(csv_bytes),
            content_type="text/csv"
        )
        print("Raw transaction CSV uploaded to MinIO.")
    except Exception as e:
        print(f"Error connecting/uploading to MinIO: {e}")
        print("Please ensure MinIO container is running before attempting upload.")

if __name__ == "__main__":
    print("Starting SentraFlow seed data script...")
    try:
        conn = get_db_connection()
        reset_database(conn)
        seed_users(conn)
        seed_model_registry(conn)
        seed_pii_rules(conn)
        seed_data_catalog(conn)
        seed_warehouse_marts(conn)
        conn.close()
        print("Database seeding completed.")
        
        upload_raw_to_minio()
        print("SentraFlow Seeding Completed Successfully.")
    except Exception as e:
        print(f"Seeding failed: {e}")
        sys.exit(1)
