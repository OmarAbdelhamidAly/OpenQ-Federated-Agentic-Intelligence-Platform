terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket         = "openq-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "openq-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
}

# KMS Key for infrastructure encryption
resource "aws_kms_key" "main" {
  description             = "KMS key for OpenQ infrastructure"
  enable_key_rotation     = true
  deletion_window_in_days = 7
  tags                    = var.tags
}

# ── Global DNS (Route 53) ────────────────────────────────────
resource "aws_route53_zone" "main" {
  name = var.domain_name
  tags = var.tags
}

# ── Application Load Balancer (Public) ───────────────────────
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  description = "Public ALB Security Group"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnet_ids

  tags = var.tags
}

# ── Kubernetes Provider Configuration ────────────────────────
provider "kubernetes" {
  host                   = module.eks.endpoint
  cluster_ca_certificate = base64decode(module.eks.kubeconfig-certificate-authority-data)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_id]
    command     = "aws"
  }
}

# 1. Networking Layer
module "vpc" {
  source       = "./modules/vpc"
  project_name = var.project_name
  aws_region   = var.aws_region
  vpc_cidr     = var.vpc_cidr
  tags         = var.tags
}

# 2. Compute Layer (Kubernetes)
module "eks" {
  source             = "./modules/eks"
  project_name       = var.project_name
  cluster_name       = var.cluster_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  node_instance_type = var.node_instance_type
  kms_key_id         = aws_kms_key.main.arn
  tags               = var.tags
}

# 3. Managed Database Layer (Aurora)
module "database" {
  source             = "./modules/database"
  project_name       = var.project_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  db_instance_class  = var.db_instance_class
  kms_key_id         = aws_kms_key.main.arn
  tags               = var.tags
}

# 4. Managed Caching Layer (Redis)
module "cache" {
  source             = "./modules/cache"
  project_name       = var.project_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  kms_key_id         = aws_kms_key.main.arn
  tags               = var.tags
}

# 5. Image Registry Layer (ECR)
module "ecr" {
  source       = "./modules/ecr"
  project_name = var.project_name
  tags         = var.tags
}

# 6. CI/CD Credentials Layer (IAM)
module "iam_cicd" {
  source       = "./modules/iam-cicd"
  project_name = var.project_name
  tags         = var.tags
}

# ── Route 53 DNS Record (Alias to ALB) ───────────────────────
resource "aws_route53_record" "www" {
  zone_id = aws_route53_zone.main.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
