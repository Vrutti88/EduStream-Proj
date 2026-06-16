output "eks_cluster_endpoint" {
  value = aws_eks_cluster.main.endpoint
}

output "eks_cluster_name" {
  value = aws_eks_cluster.main.name
}

output "rds_endpoint" {
  value     = data.aws_db_instance.main.endpoint
  sensitive = true
}

output "s3_bucket_name" {
  value = data.aws_s3_bucket.storage.bucket
}
