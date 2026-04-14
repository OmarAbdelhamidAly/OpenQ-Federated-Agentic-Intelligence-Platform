output "vpc_id" {
  value = module.vpc.vpc_id
}

output "eks_cluster_endpoint" {
  value = module.eks.endpoint
}

output "aurora_db_endpoint" {
  value = module.database.db_endpoint
}

output "redis_primary_endpoint" {
  value = module.cache.redis_primary_endpoint
}

output "kubeconfig_command" {
  value = "aws eks update-kubeconfig --region ${var.aws_region} --name ${var.cluster_name}"
}
