# INTENTIONALLY INSECURE — Checkov test fixture (Terraform).
# Not deployed anywhere; exists only so Checkov has IaC misconfigurations to detect.
# Do not copy these patterns.

resource "aws_s3_bucket" "public_data" {
  bucket = "deliveryos-sample-public-bucket"
  # CKV: public-read ACL exposes the bucket contents to the world.
  acl    = "public-read"
}

resource "aws_s3_bucket_public_access_block" "public_data" {
  bucket                  = aws_s3_bucket.public_data.id
  # CKV: all public-access protections disabled.
  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_security_group" "wide_open" {
  name        = "wide-open-sg"
  description = "Sample insecure security group"

  # CKV: SSH open to the entire internet (0.0.0.0/0).
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # CKV: all egress allowed.
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
