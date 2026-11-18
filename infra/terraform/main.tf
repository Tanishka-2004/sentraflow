# SentraFlow Governed Lakehouse - Core Terraform Definition
#
# MONTHLY COST ESTIMATION (ap-south-1, Production):
# -------------------------------------------------------------
# 1. S3 Storage (500 GB Medallion + Lifecycle Glacier): ~$12.50 / month
# 2. AWS KMS CMK (1 key for SSE-KMS):                    ~$1.00 / month
# 3. AWS Glue Data Catalog (1M objects):                 ~$1.00 / month
# 4. Athena Queries (Pay-per-scan, 100 GB/mo):           ~$0.50 / month
# 5. AWS MSK (2x kafka.m5.large, if enabled):            ~$145.00 / month
# Total estimated cloud infrastructure:                   ~$160.00 / month (or ~$15 without MSK)
#
# TEARDOWN & DESTROY SAFETY:
# To safely deprovision all resources without leaving orphaned storage:
#   1. Empty S3 versioned buckets: aws s3 rm s3://<bucket> --recursive
#   2. Run: terraform destroy -auto-approve

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
      Compliance  = "RBI-Banking-PII-Protected"
    }
  }
}

# Customer Managed Key (CMK) for Envelope Encryption
resource "aws_kms_key" "lakehouse_key" {
  description             = "SentraFlow Lakehouse Customer Managed Key for S3, Athena, and CloudWatch"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  tags = {
    Name = "${var.project_name}-kms-cmk"
  }
}

resource "aws_kms_alias" "lakehouse_key_alias" {
  name          = "alias/${var.project_name}-key"
  target_key_id = aws_kms_key.lakehouse_key.key_id
}

