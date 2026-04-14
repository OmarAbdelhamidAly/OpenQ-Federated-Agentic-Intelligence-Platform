output "db_endpoint" {
  value = aws_rds_cluster.main.endpoint
}

output "db_cluster_id" {
  value = aws_rds_cluster.main.id
}
