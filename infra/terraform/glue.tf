# AWS Glue Data Catalog Configuration

resource "aws_glue_catalog_database" "bronze" {
  name        = "${var.project_name}_bronze"
  description = "SentraFlow Bronze Layer Raw Append-Only Ingestion Delta Tables"
}

resource "aws_glue_catalog_database" "silver" {
  name        = "${var.project_name}_silver"
  description = "SentraFlow Silver Layer Clean, Conformed, Masked Delta Tables"
}

resource "aws_glue_catalog_database" "gold" {
  name        = "${var.project_name}_gold"
  description = "SentraFlow Gold Layer Star Schema Dimensions, Facts, and Marts"
}

# Example Gold Mart Glue Table Definition
resource "aws_glue_catalog_table" "gold_customer_360" {
  name          = "mart_customer_360"
  database_name = aws_glue_catalog_database.gold.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "classification" = "delta"
    "typeOfData"     = "file"
  }

  storage_descriptor {
    location      = "s3://${aws_s3_bucket.lakehouse_buckets["gold"].bucket}/marts/mart_customer_360"
    input_format  = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat"
    output_format = "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat"

    ser_de_info {
      serialization_library = "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"
    }

    columns {
      name = "customer_id"
      type = "string"
    }
    columns {
      name = "pan_masked"
      type = "string"
    }
    columns {
      name = "email_masked"
      type = "string"
    }
    columns {
      name = "total_txns"
      type = "bigint"
    }
    columns {
      name = "total_spend_inr"
      type = "double"
    }
  }
}

