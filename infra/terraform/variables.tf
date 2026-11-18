# Terraform Variables for SentraFlow Data Lakehouse Infrastructure

variable "aws_region" {
  description = "AWS deployment region"
  type        = string
  default     = "ap-south-1" # Mumbai region for Indian banking data residency
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "project_name" {
  description = "Project name prefix for resources"
  type        = string
  default     = "sentraflow"
}

variable "lakehouse_bucket_prefix" {
  description = "Globally unique prefix for lakehouse S3 buckets"
  type        = string
  default     = "sentraflow-lakehouse"
}

variable "enable_msk" {
  description = "Whether to provision real AWS MSK cluster or use local/EC2 Kafka"
  type        = bool
  default     = false
}

