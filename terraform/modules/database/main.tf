resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = var.private_subnet_ids

  tags = var.tags
}

resource "aws_security_group" "db" {
  name        = "${var.project_name}-db-sg"
  description = "Allow inbound traffic to Postgres from EKS nodes"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/16"] # Should be refined to EKS node SG
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = var.tags
}

resource "aws_rds_cluster" "main" {
  cluster_identifier      = "${var.project_name}-aurora-cluster"
  engine                  = "aurora-postgresql"
  engine_mode             = "provisioned" # Default for Serverless v2
  engine_version          = "16.1"
  database_name           = "analyst_agent"
  master_username         = "postgres"
  master_password         = "openq_secure_password_123" # Should be in AWS Secrets Manager
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.db.id]
  skip_final_snapshot     = true

  serverlessv2_scaling_configuration {
    max_capacity = var.db_instance_class.max
    min_capacity = var.db_instance_class.min
  }

  tags = var.tags
}

resource "aws_rds_cluster_instance" "main" {
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  tags = var.tags
}
