terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
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
# Manual ALB removed. 
# ALB is managed by AWS Load Balancer Controller (installed via Helm below)
# which reads the alb-ingress.yaml manifest in Kubernetes.

# ── Kubernetes & Helm Provider Configuration ─────────────────
provider "kubernetes" {
  host                   = module.eks.endpoint
  cluster_ca_certificate = base64decode(module.eks.kubeconfig-certificate-authority-data)
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_id]
    command     = "aws"
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.endpoint
    cluster_ca_certificate = base64decode(module.eks.kubeconfig-certificate-authority-data)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_id]
      command     = "aws"
    }
  }
}

# ── Infrastructure Helm Releases ─────────────────────────────
# 1. AWS Load Balancer Controller
resource "helm_release" "aws_load_balancer_controller" {
  name       = "aws-load-balancer-controller"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  namespace  = "kube-system"
  
  set {
    name  = "clusterName"
    value = module.eks.cluster_id
  }
  
  # Role ARN is provided by EKS module output
  set {
    name  = "serviceAccount.create"
    value = "true"
  }
  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.eks.aws_lbc_role_arn
  }
  depends_on = [module.eks]
}

# 2. External Secrets Operator
resource "helm_release" "external_secrets" {
  name             = "external-secrets"
  repository       = "https://charts.external-secrets.io"
  chart            = "external-secrets"
  namespace        = "external-secrets"
  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
  }
  depends_on = [module.eks]
}

# 3. Kube-Prometheus-Stack (Observability Layer)
resource "helm_release" "kube_prometheus_stack" {
  name             = "prometheus-stack"
  repository       = "https://prometheus-community.github.io/helm-charts"
  chart            = "kube-prometheus-stack"
  namespace        = "monitoring"
  create_namespace = true

  set {
    name  = "grafana.adminPassword"
    value = "admin" # In production, this should be pulled from Secrets Manager
  }
  
  set {
    name  = "alertmanager.enabled"
    value = "false"
  }

  depends_on = [module.eks]
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

# 7. DocumentDB Layer (JSON Pillar)
module "documentdb" {
  source             = "./modules/documentdb"
  project_name       = var.project_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  kms_key_id         = aws_kms_key.main.arn
  tags               = var.tags
}

# 8. Shared Storage Layer (EFS for HuggingFace Cache & Tenant Uploads)
module "efs" {
  source             = "./modules/efs"
  project_name       = var.project_name
  vpc_id             = module.vpc.vpc_id
  private_subnet_ids = module.vpc.private_subnet_ids
  kms_key_id         = aws_kms_key.main.arn
  tags               = var.tags
}

# ── Route 53 DNS Record ──────────────────────────────────────
# Note: The Route53 Alias to the ALB will now be managed via External-DNS
# or manually in the UI since the ALB name is generated dynamically by K8s.
