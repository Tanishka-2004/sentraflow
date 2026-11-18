# Least-Privilege IAM Roles and Policies for SentraFlow Lakehouse

# 1. Airflow Orchestrator Role
resource "aws_iam_role" "airflow_role" {
  name = "${var.project_name}-airflow-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "airflow.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "airflow_policy" {
  name = "${var.project_name}-airflow-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "BronzeAndQuarantineAccess"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.lakehouse_buckets["bronze"].arn,
          "${aws_s3_bucket.lakehouse_buckets["bronze"].arn}/*",
          aws_s3_bucket.lakehouse_buckets["quarantine"].arn,
          "${aws_s3_bucket.lakehouse_buckets["quarantine"].arn}/*",
        ]
      },
      {
        Sid    = "GlueJobTrigger"
        Effect = "Allow"
        Action = ["glue:StartJobRun", "glue:GetJobRun", "glue:GetJobRuns"]
        Resource = "*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "airflow_attach" {
  role       = aws_iam_role.airflow_role.name
  policy_arn = aws_iam_policy.airflow_policy.arn
}

# 2. Spark Governance PII Gate Role (CRITICAL SECURITY ROLE)
# THE ONLY ROLE PERMITTED TO WRITE TO S3 SILVER BUCKET
resource "aws_iam_role" "spark_gate_role" {
  name = "${var.project_name}-spark-gate-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "emr-serverless.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "spark_gate_policy" {
  name = "${var.project_name}-spark-gate-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadBronzeForScanning"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.lakehouse_buckets["bronze"].arn,
          "${aws_s3_bucket.lakehouse_buckets["bronze"].arn}/*"
        ]
      },
      {
        Sid      = "ExclusiveSilverPutObjectPermission"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:AbortMultipartUpload"]
        Resource = "${aws_s3_bucket.lakehouse_buckets["silver"].arn}/*"
      },
      {
        Sid      = "KMSDecryptionEncryption"
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.lakehouse_key.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "gate_attach" {
  role       = aws_iam_role.spark_gate_role.name
  policy_arn = aws_iam_policy.spark_gate_policy.arn
}

# 3. Spark Gold Marts Materialization Role
resource "aws_iam_role" "spark_gold_role" {
  name = "${var.project_name}-spark-gold-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "emr-serverless.amazonaws.com" }
    }]
  })
}

resource "aws_iam_policy" "spark_gold_policy" {
  name = "${var.project_name}-spark-gold-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadSilverConformed"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.lakehouse_buckets["silver"].arn,
          "${aws_s3_bucket.lakehouse_buckets["silver"].arn}/*"
        ]
      },
      {
        Sid      = "WriteGoldMarts"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.lakehouse_buckets["gold"].arn,
          "${aws_s3_bucket.lakehouse_buckets["gold"].arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "gold_attach" {
  role       = aws_iam_role.spark_gold_role.name
  policy_arn = aws_iam_policy.spark_gold_policy.arn
}

# 4. Analyst Athena Role (Least privilege query access on Gold only)
resource "aws_iam_role" "analyst_role" {
  name = "${var.project_name}-analyst-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { AWS = "arn:aws:iam::123456789012:root" }
    }]
  })
}

resource "aws_iam_policy" "analyst_policy" {
  name = "${var.project_name}-analyst-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadGoldOnly"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:ListBucket"]
        Resource = [
          aws_s3_bucket.lakehouse_buckets["gold"].arn,
          "${aws_s3_bucket.lakehouse_buckets["gold"].arn}/*"
        ]
      },
      {
        Sid      = "AthenaQueryExecution"
        Effect   = "Allow"
        Action   = [
          "athena:StartQueryExecution",
          "athena:GetQueryExecution",
          "athena:GetQueryResults",
          "athena:StopQueryExecution"
        ]
        Resource = aws_athena_workgroup.analytics.arn
      },
      {
        Sid      = "WriteQueryResultsToArtifacts"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = "${aws_s3_bucket.lakehouse_buckets["artifacts"].arn}/athena-results/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "analyst_attach" {
  role       = aws_iam_role.analyst_role.name
  policy_arn = aws_iam_policy.analyst_policy.arn
}

