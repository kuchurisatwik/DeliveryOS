# INTENTIONALLY INSECURE — Terraform fixture (Checkov + Trivy IaC misconfig).

provider "aws" {
  region = "us-east-1"
}

# Checkov: security group open to the world
resource "aws_security_group" "open" {
  name = "allow-all"
  ingress {
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Checkov: public-read S3 bucket, unencrypted
resource "aws_s3_bucket" "public" {
  bucket = "multilang-public-bucket"
  acl    = "public-read"
}


# Checkov: unencrypted, publicly accessible RDS with hardcoded password
resource "aws_db_instance" "db" {
  allocated_storage   = 20
  engine              = "mysql"
  instance_class      = "db.t2.micro"
  username            = "admin"
  password            = "changeme-please"
  storage_encrypted   = false
  publicly_accessible = true
}
