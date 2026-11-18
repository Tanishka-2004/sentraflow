"""
Command-line interface for the SentraFlow financial data generator.
"""

import argparse
from pathlib import Path

from data_generator.generator import FinancialDataGenerator
from data_generator.producer import KafkaStreamProducer
from data_generator.writer import export_batch_to_landing


def main():
    parser = argparse.ArgumentParser(
        description="SentraFlow Synthetic Financial Data Generator"
    )
    parser.add_argument(
        "--customers", type=int, default=1000, help="Number of customers to generate"
    )
    parser.add_argument(
        "--txns", type=int, default=5000, help="Number of transactions to generate"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--dirty-rate",
        type=float,
        default=0.03,
        help="Rate of dirty data injection (0.0 to 1.0)",
    )
    parser.add_argument(
        "--fraud-rate",
        type=float,
        default=0.015,
        help="Rate of fraud pattern injection (~1-2%%)",
    )
    parser.add_argument(
        "--format",
        choices=["parquet", "csv"],
        default="parquet",
        help="Landing file format",
    )
    parser.add_argument(
        "--output-dir",
        "--landing-dir",
        dest="output_dir",
        type=str,
        default="./landing",
        help="Landing zone output directory",
    )
    parser.add_argument(
        "--batch-id", type=str, default="batch_001", help="Batch identifier"
    )
    parser.add_argument(
        "--with-scd-updates", action="store_true", help="Generate customer SCD updates"
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Stream transactions to Kafka topic txn.raw",
    )
    parser.add_argument(
        "--eps",
        "--events-per-second",
        dest="eps",
        type=float,
        default=20.0,
        help="Events per second for streaming",
    )
    parser.add_argument(
        "--kafka-servers",
        type=str,
        default="localhost:9092",
        help="Kafka bootstrap servers",
    )

    args = parser.parse_args()

    print(
        f"[*] Initializing FinancialDataGenerator (seed={args.seed}, dirty={args.dirty_rate}, fraud={args.fraud_rate})"
    )
    generator = FinancialDataGenerator(
        seed=args.seed,
        dirty_rate=args.dirty_rate,
        fraud_rate=args.fraud_rate,
    )

    print(f"[*] Generating {args.customers} customers...")
    customers = generator.generate_customers(count=args.customers)

    print("[*] Generating accounts...")
    accounts = generator.generate_accounts()

    print("[*] Generating merchants...")
    merchants = generator.generate_merchants()

    print(f"[*] Generating {args.txns} transactions...")
    txns = generator.generate_transactions(count=args.txns)

    # Write batch landing files
    output_path = Path(args.output_dir)
    print(
        f"[*] Writing batch landing files to {output_path.resolve()} ({args.format})..."
    )

    c_path = export_batch_to_landing(
        customers, "customers", args.output_dir, args.format, args.batch_id
    )
    a_path = export_batch_to_landing(
        accounts, "accounts", args.output_dir, args.format, args.batch_id
    )
    m_path = export_batch_to_landing(
        merchants, "merchants", args.output_dir, args.format, args.batch_id
    )
    t_path = export_batch_to_landing(
        txns, "transactions", args.output_dir, args.format, args.batch_id
    )

    print(f"    - Customers:    {c_path}")
    print(f"    - Accounts:     {a_path}")
    print(f"    - Merchants:    {m_path}")
    print(f"    - Transactions: {t_path}")

    if args.with_scd_updates:
        print("[*] Generating SCD Type 2 customer mutations...")
        updates = generator.generate_customer_updates(update_ratio=0.08)
        u_path = export_batch_to_landing(
            updates,
            "customers",
            args.output_dir,
            args.format,
            f"{args.batch_id}_scd_updates",
        )
        print(f"    - Customer Updates: {u_path}")

    if args.stream:
        print(f"[*] Streaming transactions to Kafka at {args.eps} EPS...")
        producer = KafkaStreamProducer(bootstrap_servers=args.kafka_servers)
        streamed = producer.stream_transactions(txns, events_per_second=args.eps)
        print(f"[*] Streamed {streamed} events.")

    print("[+] Phase 1 Data Generation complete successfully!")


if __name__ == "__main__":
    main()
