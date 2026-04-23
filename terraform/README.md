<div align="center">

# ☁️ OpenQ Enterprise AWS Infrastructure (Terraform)
**Infrastructure as Code (IaC) — Definitive Architecture Guide**

[![Terraform](https://img.shields.io/badge/Terraform-1.5+-7B42BC?logo=terraform&logoColor=white)](https://terraform.io)
[![AWS](https://img.shields.io/badge/AWS-5.0+-232F3E?logo=amazon-aws&logoColor=white)](https://aws.amazon.com)

</div>

---

## 🏗️ Architectural Philosophy

As a Cloud Architect with two decades of experience designing distributed systems on AWS, I architected this repository to reflect the highest standards of **Enterprise Cloud-Native Infrastructure**. 

In this environment, Terraform is not treated as a mere server-provisioning script. It is an **Immutable State Machine** designed to guarantee strict High Availability, Least Privilege Security, and aggressive Cost Optimization (achieved by strategically blending Spot Instances with Serverless Database compute).

---

## 🗂️ Project Structure & Module Dependency Graph

The infrastructure is built upon a **Modular Architecture** to ensure maintainability, blast-radius isolation, and environment reproducibility (Dev, Staging, Prod). There is no Single Point of Failure (SPOF), and each module adheres strictly to the Single Responsibility Principle.

```mermaid
graph TD
    A[main.tf (Root Configuration)] --> B(VPC Module)
    A --> C(KMS Key Encryption)
    
    B --> D(EKS Module)
    B --> E(Database Module - Aurora)
    B --> F(Cache Module - ElastiCache)
    B --> G(DocumentDB Module)
    B --> H(EFS Module)
    
    C -. Encrypts .-> D
    C -. Encrypts .-> E
    C -. Encrypts .-> F
    C -. Encrypts .-> G
    C -. Encrypts .-> H
    
    D --> I[Helm: AWS Load Balancer Controller]
    D --> J[Helm: External Secrets Operator]
    D --> M[Helm: Kube-Prometheus-Stack]
    
    K[ECR Module] -. Independent .-> A
    L[IAM CI/CD Module] -. Independent .-> A
```

---

## 🔍 Deep Dive: Root Configuration

### 1. `main.tf` (The Control Plane)
This is the heart of the infrastructure. It contains no raw resource drafts; instead, it wires the modules together cleanly. 
Key highlights:
*   **Providers:** Leverages 3 core providers (`aws`, `kubernetes`, `helm`).
*   **Helm Releases:** We avoid manual `aws_lb` provisioning (which is an anti-pattern in modern Kubernetes). Instead, we inject the `aws-load-balancer-controller`, `external-secrets` operator, and the `kube-prometheus-stack` into the cluster, granting the EKS environment the autonomy to manage its own AWS resources and self-monitoring.
*   **KMS Encryption:** A centralized Customer Managed Key (`aws_kms_key.main`) is generated and passed to all stateful modules to guarantee Data-At-Rest Encryption by default.

### 2. `variables.tf` & `outputs.tf`
*   `variables.tf`: Defines centralized parameters such as `vpc_cidr`, `aws_region`, and node instance types (e.g., `t3.medium`).
*   `outputs.tf`: Exports critical ARNs and Endpoints (like the EKS Kubeconfig data) required by downstream CI/CD pipelines.

---

## 🧩 Deep Dive: Infrastructure Modules

Not a single file is left to chance. Every module is hardened for production workloads:

### 🌐 `modules/vpc` (Network Foundation)
*   **Architecture:** Provisions a custom VPC CIDR block, segmented into Public Subnets (strictly for NAT Gateways and ALBs) and Private Subnets.
*   **Security:** EKS Nodes and Databases are isolated exclusively within Private Subnets, neutralizing direct inbound internet threats.

### ⛴️ `modules/eks` (The Cognitive Compute Layer)
This module represents the computational brain of the platform. It has been heavily customized to isolate distinct workloads:
*   **OIDC & IRSA:** Integrates an OpenID Connect Provider to grant Kubernetes Service Accounts real IAM permissions (e.g., allowing the ALB Controller to spin up load balancers) without ever exposing long-lived access keys.
*   **`core-nodes` (On-Demand):** A dedicated node group for stable, stateless components (API Gateway, Frontend). Guarantees 100% stability.
*   **`worker-nodes` (Spot Instances):** A high-compute node group reserved for heavy asynchronous tasks (PDF Parsing, Audio Diarization). Utilizing Spot instances slashes compute costs by up to 70%. Interruption recovery is handled natively by the Celery task broker.

### 🗄️ `modules/database` (Relational Pillar)
*   **Aurora Serverless v2:** Traditional RDS was bypassed in favor of Aurora Serverless. It automatically scales ACUs (Aurora Capacity Units) up and down based on API load, delivering exceptional performance during peak hours and near-zero costs during idle periods.

### 📄 `modules/documentdb` (JSON Pillar)
*   **NoSQL Engine:** Purpose-built for the `worker-json` service. A MongoDB-compatible cluster that inherits AWS's enterprise High Availability. Storage is fully encrypted, and master credentials are dynamically generated.

### ⚡ `modules/cache` (Message Broker)
*   **ElastiCache (Redis):** Configured with Multi-AZ deployments and Automatic Failover. Beyond simple caching, this is the high-throughput heartbeat of the Celery Message Broker, orchestrating millions of background tasks.

### 💾 `modules/efs` (Shared State)
*   **Elastic File System:** Our AI architecture demands that massive HuggingFace Models (`hf_cache`) and tenant documents (`tenant-data`) be accessible across multiple Pods concurrently (`ReadWriteMany`). This module provisions the storage and distributes Mount Targets across all Private Subnets.

### 📦 `modules/ecr` & `modules/iam-cicd`
*   **ECR:** Provisions isolated container repositories for every microservice, enforcing Image Scanning (Trivy/Clair) on push.
*   **IAM CI/CD:** Provisions Least-Privilege IAM Roles utilized by GitHub Actions / GitLab CI to securely push images and trigger EKS rollouts.

---

## 🔒 Security Posture & State Management

### 1. Terraform State (`backend "s3"`)
Infrastructure state is never stored locally. We utilize AWS S3 to store `terraform.tfstate` (with server-side encryption enabled), coupled with a **DynamoDB Table** to enforce strict State Locking. This prevents fatal corruption if multiple engineers execute `terraform apply` concurrently.

### 2. Zero-Knowledge Passwords
You will not find a single hardcoded password (Database, Redis, Neo4j) in the source code or `.tfvars` files. We utilize the `random_password` resource to generate highly complex credentials, storing them directly into **AWS Secrets Manager**. The Kubernetes `External Secrets Operator` then pulls these securely into the cluster at runtime.

---

## 🚀 Execution Guide (For DevOps)

To provision this infrastructure from scratch, execute the following sequence:

```bash
# 1. Initialize the backend and download providers
terraform init

# 2. Validate syntax and module integration
terraform validate

# 3. Review the execution plan (Verify AWS costs and IAM changes)
terraform plan -out=tfplan

# 4. Provision the infrastructure (EKS and Aurora typically require ~15 mins)
terraform apply tfplan

# 5. Fetch Kubeconfig to connect to the new cluster
aws eks update-kubeconfig --region us-east-1 --name openq-eks-cluster
```

*Architected for Resilience. Built for Scale. 🖤 OpenQ Engineering.*
