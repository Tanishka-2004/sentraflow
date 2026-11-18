import os
import sys
import json
import uuid
import time
import requests
import psycopg2
from datetime import datetime
from decimal import Decimal

# Configs
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/sentraflow")
KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def get_db_connection():
    return psycopg2.connect(DB_URL)

def validate_event(event: dict) -> bool:
    required_fields = [
        "transaction_id", "account_id", "amount", "transaction_type",
        "oldBalanceOrig", "newBalanceOrig", "oldBalanceDest", "newBalanceDest"
    ]
    return all(field in event for field in required_fields)

def process_transaction(event: dict, db_conn) -> bool:
    correlation_id = str(uuid.uuid4())
    tx_id = event["transaction_id"]
    
    cur = db_conn.cursor()
    try:
        # 1. Idempotency Check: Prevent duplicate transaction processing
        cur.execute("SELECT 1 FROM warehouse.fact_transactions WHERE transaction_id = %s", (tx_id,))
        if cur.fetchone():
            print(f"[{correlation_id}] Duplicate transaction detected: {tx_id}. Skipping.")
            return True
            
        print(f"[{correlation_id}] Processing transaction: {tx_id} | Amount: {event['amount']}")
        
        # 2. Call ML Service with Retry / Timeout Logic
        risk_score = 0.0
        risk_level = "LOW"
        shap_explanations = {}
        ml_failed = False
        
        payload = {
            "amount": float(event["amount"]),
            "oldBalanceOrig": float(event["oldBalanceOrig"]),
            "newBalanceOrig": float(event["newBalanceOrig"]),
            "oldBalanceDest": float(event["oldBalanceDest"]),
            "newBalanceDest": float(event["newBalanceDest"]),
            "transaction_type": event["transaction_type"]
        }
        
        # Retry loop for resilience (3 retries with exponential backoff)
        for attempt in range(3):
            try:
                res = requests.post(f"{ML_SERVICE_URL}/predict", json=payload, timeout=2.0)
                if res.status_code == 200:
                    data = res.json()
                    risk_score = data["risk_score"]
                    risk_level = data["risk_level"]
                    shap_explanations = data["shap_explanations"]
                    break
                else:
                    print(f"[{correlation_id}] ML Service returned status {res.status_code}, retrying...")
            except requests.RequestException as e:
                print(f"[{correlation_id}] ML Service request failed (attempt {attempt+1}): {e}")
                time.sleep(1.0 * (attempt + 1))
        else:
            # Fallback when ML API is unreachable (circuit breaker mode)
            print(f"[{correlation_id}] ML Service unreachable after 3 attempts. Falling back to pending score.")
            ml_failed = True
            risk_score = 0.0
            risk_level = "PENDING"
            
        # 3. Persist scored transaction to Gold Warehouse
        dt = datetime.now()
        date_key = int(dt.strftime("%Y%m%d"))
        is_flagged = risk_level in ["MEDIUM", "HIGH", "CRITICAL"]
        
        cur.execute("""
            INSERT INTO warehouse.fact_transactions 
            (transaction_id, account_id, date_key, amount, transaction_type, risk_score, is_flagged, source, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'stream', %s)
        """, (
            tx_id, event["account_id"], date_key, Decimal(str(event["amount"])),
            event["transaction_type"], risk_score, is_flagged, dt
        ))
        
        # 4. Trigger alert for high risk levels
        alert_id = None
        if is_flagged:
            cur.execute("""
                INSERT INTO alerts (transaction_id, risk_score, risk_level, status)
                VALUES (%s, %s, %s, 'open') RETURNING id
            """, (tx_id, risk_score, risk_level))
            alert_id = cur.fetchone()[0]
            
            # Record audit event for flagged transactions
            cur.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
            admin_user = cur.fetchone()
            admin_id = admin_user[0] if admin_user else None
            
            cur.execute("""
                INSERT INTO audit_log (actor_id, action, resource, target_id, reason, ip_address, user_agent)
                VALUES (%s, 'AUTO_ALERT_TRIGGERED', 'alerts', %s, %s, '127.0.0.1', 'Stream Consumer Engine')
            """, (admin_id, alert_id, f"Risk score exceeding threshold: {risk_score:.2f} ({risk_level})"))
            
            # Broadcast WebSocket alert to backend
            try:
                requests.post(
                    f"{BACKEND_URL}/api/internal/broadcast-alert",
                    json={
                        "id": alert_id,
                        "transaction_id": tx_id,
                        "risk_score": risk_score,
                        "risk_level": risk_level,
                        "status": "open",
                        "created_at": dt.isoformat(),
                        "shap_explanations": shap_explanations
                    },
                    timeout=1.0
                )
            except Exception as e:
                print(f"[{correlation_id}] Failed to send real-time WS notification: {e}")
                
        # 5. Record column lineage event
        cur.execute("""
            INSERT INTO lineage_events (run_id, step_name, source_table, source_column, target_table, target_column, event_type)
            VALUES (%s, 'streaming_consumer', 'kafka_topic_transactions_raw', NULL, 'fact_transactions', NULL, 'write')
        """, (f"STREAM_{correlation_id[:8]}",))
        
        db_conn.commit()
        print(f"[{correlation_id}] Successfully ingested and processed transaction: {tx_id}. Flagged: {is_flagged}")
        return True
        
    except Exception as e:
        db_conn.rollback()
        print(f"[{correlation_id}] Failed to process transaction: {e}")
        # Send failure to dead-letter queue (here represented as standard log file print)
        with open("/tmp/stream_consumer_dlq.log", "a") as dlq:
            dlq.write(f"{datetime.now().isoformat()} | TX: {tx_id} | ERROR: {str(e)} | DATA: {json.dumps(event)}\n")
        return False
    finally:
        cur.close()

def run_consumer_loop():
    print("Starting SentraFlow Stream Consumer Service...")
    
    # Try importing kafka dependencies
    kafka_available = False
    try:
        from confluent_kafka import Consumer, KafkaError
        kafka_available = True
    except ImportError:
        print("confluent-kafka not found. Running in simulated streaming mode.")
        
    db_conn = get_db_connection()
    
    if kafka_available:
        try:
            conf = {
                'bootstrap.servers': KAFKA_BROKERS,
                'group.id': 'sentraflow-group',
                'auto.offset.reset': 'earliest'
            }
            consumer = Consumer(conf)
            consumer.subscribe(['transactions.raw'])
            print(f"Subscribed to Redpanda topic 'transactions.raw' at {KAFKA_BROKERS}")
            
            while True:
                msg = consumer.poll(timeout=1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    elif msg.error().code() == 3 or "UNKNOWN_TOPIC_OR_PART" in str(msg.error().code()):
                        # Topic is not created yet, wait and retry
                        print("Topic 'transactions.raw' does not exist yet. Waiting for events to be published...")
                        time.sleep(5)
                        continue
                    else:
                        print(f"Kafka Error: {msg.error()}")
                        break
                        
                try:
                    event = json.loads(msg.value().decode('utf-8'))
                    if validate_event(event):
                        process_transaction(event, db_conn)
                    else:
                        print(f"Validation failed for schema format on message: {msg.value()}")
                except Exception as e:
                    print(f"Error parsing message: {e}")
        except KeyboardInterrupt:
            pass
        finally:
            consumer.close()
            db_conn.close()
    else:
        # Simulated generator loop for demo resiliency
        print("Simulated loop started. Generating transaction streams...")
        try:
            first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer"]
            last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones"]
            
            sim_count = 0
            while True:
                sim_count += 1
                tx_id = f"TX_STREAM_{sim_count:05d}"
                acc_id = f"ACC_{random_int(1, 50):04d}_{random_int(0, 1)}"
                
                # Mock typical transaction
                amount = float(round(10 + (2.5 ** float(random_float(2.0, 7.0))), 2))
                tx_type = "TRANSFER" if random_float(0, 1) > 0.7 else "CASH_OUT"
                
                # Force alert trigger on every 10th transaction for UI dashboard demo
                is_fraud_sim = (sim_count % 10 == 0)
                if is_fraud_sim:
                    amount = float(random_float(15000, 30000))
                    old_orig = amount
                    new_orig = 0.0
                    old_dest = 120.0
                    new_dest = 120.0 # Error: dest not credited (fraud)
                else:
                    old_orig = amount + float(random_float(50, 1000))
                    new_orig = old_orig - amount
                    old_dest = float(random_float(0, 500))
                    new_dest = old_dest + amount
                    
                event = {
                    "transaction_id": tx_id,
                    "account_id": acc_id,
                    "amount": amount,
                    "transaction_type": tx_type,
                    "oldBalanceOrig": old_orig,
                    "newBalanceOrig": new_orig,
                    "oldBalanceDest": old_dest,
                    "newBalanceDest": new_dest
                }
                
                process_transaction(event, db_conn)
                
                # Sleep for 15 seconds between simulated transactions
                time.sleep(15.0)
                
        except KeyboardInterrupt:
            print("Simulated loop stopped.")
        finally:
            db_conn.close()

def random_float(low, high) -> float:
    # Standalone seedless random logic
    t = time.time()
    seed = int(t * 1000) % 100000
    r = (seed % 1000) / 1000.0
    return float(low + r * (high - low))

def random_int(low, high) -> int:
    return int(random_float(low, high + 0.99))

if __name__ == "__main__":
    run_consumer_loop()
