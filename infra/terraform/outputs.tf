# Terraform Outputs for SentraFlow Data Platform

output "kms_key_arn" {
  description = "KMS Customer Managed Key ARN for envelope encryption"
  value       = aws_kms_key.lakehouse_key.arn
}

output "s3_bucket_arns" {
  description = "ARNs of all provisioned S3 medallion buckets"
  value       = { for k, v in aws_s3_bucket.lakehouse_buckets : k => v.arn }
}

output "athena_workgroup_name" {
  description = "Name of provisioned Athena analytics workgroup"
  value       = aws_athena_workgroup.analytics.name
}

output "iam_role_arns" {
  description = "IAM role ARNs enforcing least-privilege medallion boundaries"
  value = {
    airflow_role    = aws_iam_role.airflow_role.arn
    spark_gate_role = aws_iam_role.spark_gate_role.arn
    spark_gold_role = aws_iam_role.spark_gold_role.arn
    analyst_role    = aws_iam_role.analyst_role.arn
  }
}

output "msk_bootstrap_brokers" {
  description = "Kafka broker connection string"
  value       = var.enable_msk ? aws_msk_cluster.kafka_cluster[0].bootstrap_brokers_tls : "localhost:9092"
}

