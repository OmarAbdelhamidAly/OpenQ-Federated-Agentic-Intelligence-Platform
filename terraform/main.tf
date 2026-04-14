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
  tags               = var.tags
}

# 3. Managed Database Layer (Aurora)
module "database" {
  source             = "./modules/database"
  project_name       = var.project_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  db_instance_class  = var.db_instance_class
  tags               = var.tags
}

# 4. Managed Caching Layer (Redis)
module "cache" {
  source             = "./modules/cache"
  project_name       = var.project_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
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
