data "aws_db_instance" "main" {
  db_instance_identifier = "edustream-db"
}

# --- S3 bucket for recordings, logs, DR backups ---
resource "aws_s3_bucket" "storage" {
  bucket = "${var.project_name}-storage-${data.aws_caller_identity.current.account_id}"
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket_versioning" "storage" {
  bucket = aws_s3_bucket.storage.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_iam_role" "replication_role" {
  name = "${var.project_name}-s3-replication-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
    }]
  })
}

# --- CloudWatch alarms for cluster health ---
resource "aws_cloudwatch_metric_alarm" "node_cpu_high" {
  alarm_name          = "${var.project_name}-node-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Triggers when node CPU exceeds 80% for 10 minutes"
}

resource "aws_cloudwatch_log_group" "app_logs" {
  name              = "/eks/${var.project_name}/app"
  retention_in_days = 14
}
