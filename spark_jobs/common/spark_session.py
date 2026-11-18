"""
Spark Session Provider for SentraFlow.

Initializes PySpark sessions configured with Delta Lake 3.2, AWS S3 / MinIO
storage connectors, and Hive catalog options.
"""

import os


def get_spark_session(
    app_name: str = "SentraFlow-Engine",
    master: str = "local[*]",
    enable_s3a: bool = True,
):
    """
    Builds or retrieves a PySpark session configured with Delta Lake and MinIO/S3.
    """
    try:
        from pyspark.sql import SparkSession
    except ImportError as e:
        raise RuntimeError(
            "PySpark is not installed in the local host environment. "
            "For full cluster execution, run within the SentraFlow Docker Spark container."
        ) from e

    s3_endpoint = os.getenv("S3_ENDPOINT", "http://localhost:9000")
    s3_access_key = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
    s3_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")

    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config(
            "spark.delta.logStore.class",
            "org.apache.spark.sql.delta.storage.S3SingleDriverLogStore",
        )
    )

    if enable_s3a:
        builder = (
            builder.config("spark.hadoop.fs.s3a.endpoint", s3_endpoint)
            .config("spark.hadoop.fs.s3a.access.key", s3_access_key)
            .config("spark.hadoop.fs.s3a.secret.key", s3_secret_key)
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config(
                "spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem"
            )
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        )

    return builder.getOrCreate()
