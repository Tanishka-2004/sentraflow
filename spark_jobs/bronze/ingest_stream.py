"""
Bronze Layer Streaming Ingestion for SentraFlow.

Consumes real-time financial transactions from Kafka topic 'txn.raw'
and appends them into the Bronze transactions Delta table with full metadata.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from deltalake import write_deltalake

from spark_jobs.common.hash_utils import compute_record_hash


class BronzeStreamIngestor:
    """
    Micro-batch / event streaming consumer appending raw events to Bronze Delta Lake.
    """

    def __init__(
        self,
        bronze_base_path: str = "./data/delta/bronze",
    ):
        self.bronze_base_path = bronze_base_path
        self.table_path = str(Path(bronze_base_path) / "transactions")

    def ingest_records(
        self,
        records: list[dict[str, Any]],
        batch_id: str = "stream_batch_001",
        schema_version: str = "v1.0",
    ) -> int:
        """
        Ingests a micro-batch of streaming records into Bronze transactions Delta table.
        """
        if not records:
            return 0

        df = pd.DataFrame(records)
        now = datetime.now(timezone.utc)
        ingest_ts_iso = now.isoformat()
        ingest_date_str = now.strftime("%Y-%m-%d")

        # Enrich with Bronze metadata
        df["_ingest_ts"] = ingest_ts_iso
        df["_source_file"] = "kafka:txn.raw"
        df["_batch_id"] = batch_id
        df["_schema_version"] = schema_version
        df["ingest_date"] = ingest_date_str

        # Deterministic record hash
        record_dicts = df.to_dict(orient="records")
        df["_record_hash"] = [compute_record_hash(r) for r in record_dicts]

        target_dir = Path(self.table_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        write_deltalake(
            self.table_path,
            df,
            mode="append",
            partition_by=["ingest_date"],
            schema_mode="merge",
        )

        return len(df)


def run_spark_structured_streaming(
    kafka_servers: str = "localhost:9092",
    topic: str = "txn.raw",
    checkpoint_location: str = "s3://sentraflow-artifacts/checkpoints/bronze_txn",
    output_table_path: str = "s3://sentraflow-bronze/transactions",
):
    """
    PySpark Structured Streaming job template for cluster deployment.
    """
    from pyspark.sql import functions as F

    from spark_jobs.common.spark_session import get_spark_session

    spark = get_spark_session(app_name="SentraFlow-Bronze-Streaming")

    df_stream = (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", kafka_servers)
        .option("subscribe", topic)
        .option("startingOffsets", "latest")
        .load()
    )

    df_parsed = (
        df_stream.selectExpr("CAST(value AS STRING) as raw_json")
        .withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_source_file", F.lit(f"kafka:{topic}"))
        .withColumn("_batch_id", F.expr("uuid()"))
        .withColumn("_schema_version", F.lit("v1.0"))
        .withColumn("ingest_date", F.to_date(F.col("_ingest_ts")))
        .withColumn("_record_hash", F.sha2(F.col("raw_json"), 256))
    )

    query = (
        df_parsed.writeStream.format("delta")
        .outputMode("append")
        .partitionBy("ingest_date")
        .option("checkpointLocation", checkpoint_location)
        .start(output_table_path)
    )

    query.awaitTermination()
