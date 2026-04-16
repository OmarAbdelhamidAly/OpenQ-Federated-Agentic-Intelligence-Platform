variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name for resource tagging"
  type        = string
  default     = "openq"
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "openq-eks-cluster"
}

variable "node_instance_type" {
  description = "Instance type for EKS worker nodes"
  type        = string
  default     = "t3.large"
}

variable "db_instance_class" {
  description = "Instance class for Aurora Serverless v2 (min/max ACUs)"
  type        = map(number)
  default = {
    min = 0.5
    max = 2.0
  }
}

variable "domain_name" {
  description = "Domain name for Route 53 and ALB (e.g., openq.ai)"
  type        = string
  default     = "openq.ai"
}

variable "tags" {
  description = "Common tags for resources"
  type        = map(string)
  default = {
    Project     = "OpenQ"
    Owner       = "Analyst"
    Environment = "Production"
    ManagedBy   = "Terraform"
  }
}
