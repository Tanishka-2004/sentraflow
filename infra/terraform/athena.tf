# AWS Athena Analytics Workgroup

resource "aws_athena_workgroup" "analytics" {
  name        = "${var.project_name}-analytics"
  description = "Governed Athena Workgroup for SentraFlow Lakehouse Mart Analysis"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = 10737418240 # 10 GB scan limit per query

    result_configuration {
      output_location = "s3://${aws_s3_bucket.lakehouse_buckets["artifacts"].bucket}/athena-results/"

      encryption_configuration {
        encryption_option = "SSE_KMS"
        kms_key_arn       = aws_kms_key.lakehouse_key.arn
      }
    }
  }

  tags = {
    Name = "${var.project_name}-athena-workgroup"
  }
}

