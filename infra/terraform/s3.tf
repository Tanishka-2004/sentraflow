# S3 Storage Architecture for SentraFlow Medallion Lakehouse

locals {
  layers = ["bronze", "silver", "gold", "quarantine", "artifacts"]
}

# 1. Medallion Layer S3 Buckets
resource "aws_s3_bucket" "lakehouse_buckets" {
  for_each = toset(locals.layers)

  bucket        = "${var.lakehouse_bucket_prefix}-${each.key}-${var.environment}"
  force_destroy = var.environment != "prod"

  tags = {
    Name  = "${var.project_name}-${each.key}"
    Layer = each.key
  }
}

# 2. Bucket Versioning
resource "aws_s3_bucket_versioning" "versioning" {
  for_each = aws_s3_bucket.lakehouse_buckets

  bucket = each.value.id
  versioning_configuration {
    status = "Enabled"
  }
}

# 3. KMS Customer-Managed Key Encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "kms_encryption" {
  for_each = aws_s3_bucket.lakehouse_buckets

  bucket = each.value.id

  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.lakehouse_key.arn
      sse_algorithm     = "aws:kms"
    }
  }
}

# 4. Public Access Block (Strict zero public access)
resource "aws_s3_bucket_public_access_block" "public_block" {
  for_each = aws_s3_bucket.lakehouse_buckets

  bucket = each.value.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 5. Lifecycle Policies: Abort incomplete multipart & Glacier transition
resource "aws_s3_bucket_lifecycle_configuration" "bucket_lifecycle" {
  for_each = aws_s3_bucket.lakehouse_buckets

  bucket = each.value.id

  rule {
    id     = "abort-incomplete-multipart"
    status = "Enabled"

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  dynamic "rule" {
    for_each = each.key == "bronze" ? [1] : []
    content {
      id     = "bronze-to-glacier-after-90d"
      status = "Enabled"

      transition {
        days          = 90
        storage_class = "GLACIER"
      }
    }
  }
}

