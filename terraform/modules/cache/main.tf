resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-cache-subnet-group"
  subnet_ids = var.private_subnet_ids
}

resource "aws_security_group" "redis" {
  name        = "${var.project_name}-redis-sg"
  description = "Allow inbound traffic to Redis"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id          = "${var.project_name}-redis"
  replication_group_description = "Redis cluster for OpenQ tasks and caching"
  node_type                     = "cache.t3.medium"
  port                          = 6379
  parameter_group_name          = "default.redis7"
  automatic_failover_enabled    = true
  multi_az_enabled              = true
  num_cache_clusters            = 2
  subnet_group_name             = aws_elasticache_subnet_group.main.name
  security_group_ids            = [aws_security_group.redis.id]

  at_rest_encryption_enabled    = true
  transit_encryption_enabled    = true
  kms_key_id                    = var.kms_key_id

  tags = var.tags
}
---
# Output file for cache
