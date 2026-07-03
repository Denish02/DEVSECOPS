terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  type    = string
  default = "us-east-1"
}

# Container registry for the built cloudmart-app image.
resource "aws_ecr_repository" "cloudmart_app" {
  name                 = "cloudmart-app"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "KMS"
  }
}

# Security group for the staging/production service - only 443 in, no
# unrestricted egress.
resource "aws_security_group" "cloudmart_app" {
  name        = "cloudmart-app"
  description = "CloudMart application security group"

  ingress {
    description = "HTTPS from load balancer"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    description = "HTTPS out for dependency/package fetches"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Bucket for audit evidence / compliance artefacts referenced in the
# governance model - private, versioned, encrypted at rest.
resource "aws_s3_bucket" "compliance_evidence" {
  bucket = "cloudmart-compliance-evidence"
}

resource "aws_s3_bucket_public_access_block" "compliance_evidence" {
  bucket                  = aws_s3_bucket.compliance_evidence.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "compliance_evidence" {
  bucket = aws_s3_bucket.compliance_evidence.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "compliance_evidence" {
  bucket = aws_s3_bucket.compliance_evidence.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}
