<div align="center">

# 🏛️ OpenQ Cloud-Native Architecture Blueprint
**Definitive Guide for Kubernetes Orchestration & AWS Infrastructure as Code (Terraform)**

</div>

---

## 📖 Executive Summary

This document is the **single source of truth** for the OpenQ infrastructure. It bridges the gap between the Kubernetes application manifests (`E:\finalproject\k8s`) and the AWS Cloud resources provisioned via Terraform (`E:\finalproject\terraform`).

It is designed for DevOps Engineers, SREs, and System Architects to ensure the transition from local development to a Production-Grade AWS environment is seamless, secure, and highly scalable.

---

## 🗺️ High-Level Cloud Topology

```mermaid
architecture-beta
    group aws(cloud)[AWS Cloud Environment]
    
    group vpc(cloud)[Virtual Private Cloud (VPC)] in aws
    
    service alb(server)[AWS Application Load Balancer] in vpc
    
    group eks(cloud)[Elastic Kubernetes Service (EKS)] in vpc
    
    group core(cloud)[Core Node Group (On-Demand)] in eks
    service api(server)[API Gateway] in core
    service front(server)[React Frontend] in core
    service corp(server)[Corporate Service] in core
    
    group workers(cloud)[Worker Node Group (Spot Instances)] in eks
    service nexus(server)[Nexus Orchestrator] in workers
    service aud(server)[Audio Pillar] in workers
    service pdf(server)[PDF Pillar] in workers
    service sql(server)[SQL Pillar] in workers
    
    group data(cloud)[Managed Data Layer (Private Subnets)] in vpc
    service rds(database)[Aurora Serverless v2] in data
    service docdb(database)[Amazon DocumentDB] in data
    service redis(database)[Amazon ElastiCache] in data
    
    service efs(disk)[Amazon EFS (Shared Cache)] in aws
    service asm(key)[AWS Secrets Manager] in aws
    
    alb:B --> T:api
    alb:B --> T:corp
    api:R --> L:nexus
    nexus:B --> T:aud
    nexus:B --> T:pdf
    
    api:B --> T:rds
    nexus:R --> L:redis
```

---

## 📂 1. K8s Manifests: Strict Separation of Concerns

The Kubernetes manifests have been radically restructured to enforce security and deployment boundaries.

| Directory | Purpose | Key Components |
|---|---|---|
| `00-namespaces/` | **Logical Isolation** | Creates `openq-core` and `openq-workers` namespaces with strict `ResourceQuotas` to prevent noisy-neighbor issues. |
| `01-config/` | **State & Secrets** | Contains `ConfigMaps` and the `Secret` placeholder. *Note: Real values are injected by External Secrets Operator.* |
| `02-data-layer/` | **Stateful Services** | Local definitions for Redis, Neo4j, Qdrant, and MongoDB. Used for Staging/Local K8s. Replaced by AWS Managed services in Production. |
| `03-core-apps/` | **Stateless API** | `api-gateway.yaml`, `frontend.yaml`, `corporate.yaml`. Bound to the `core-nodes` group. |
| `04-workers/` | **Asynchronous Compute** | The Celery workers. Bound to the `worker-nodes` (Spot instances). |
| `05-autoscaling/` | **Elasticity** | HorizontalPodAutoscalers (HPAs) targeting 70% CPU utilization across all deployments. |
| `06-ingress/` | **Traffic Routing** | ALB Ingress definition mapping `/corporate` and `/api` to their respective K8s Services. |

---

## 💻 2. Compute Strategy (AWS EKS & Terraform)

To balance extreme performance requirements (PDF parsing, Audio processing) with cost-efficiency, Terraform MUST provision **two distinct EKS Node Groups**:

### A. The Core Node Group
*   **Purpose:** Host stateful infrastructure (if running local DBs) and critical stateless APIs (Gateway, Frontend).
*   **Capacity Type:** `ON_DEMAND`
*   **Instance Types:** `t3.medium` or `m5.large`.
*   **K8s Label:** `role: core`

### B. The Worker Node Group
*   **Purpose:** Host the heavy, fault-tolerant Celery workers.
*   **Capacity Type:** `SPOT` (Reduces compute costs by up to 70%).
*   **Instance Types:** Compute-optimized instances like `c5.2xlarge` or `c6i.2xlarge`.
*   **Resiliency:** Handled natively by Celery. If a Spot node is terminated, Celery will automatically re-queue unacknowledged tasks to surviving nodes.

---

## 💾 3. Data & Storage Architecture

### A. Managed Services Integration (Production)
In production, Terraform provisions managed alternatives to the `02-data-layer` manifests:
1.  **PostgreSQL → Amazon Aurora Serverless v2:** Auto-scales ACUs based on API load.
2.  **Redis → Amazon ElastiCache:** Highly available broker for Celery queues.
3.  **MongoDB → Amazon DocumentDB:** Scalable NoSQL store for the JSON Pillar.
*Note: Neo4j and Qdrant remain as K8s `StatefulSets` due to specific plugin requirements (GDS/APOC).*

### B. Shared File Systems (EFS)
The OpenQ architecture relies heavily on cross-pod file sharing. Terraform MUST provision **Amazon EFS** and the **AWS EFS CSI Driver**.
*   **`hf_cache` PVC:** Mounted across all NLP workers (PDF, Audio, Nexus) to share downloaded HuggingFace models (e.g., Llama-3, Pyannote), saving hundreds of GBs of bandwidth and local storage.
*   **`tenant-data` PVC:** Ensures that files uploaded via the API Gateway are immediately accessible by any Celery worker node.

---

## 🔐 4. Identity, Security, and Secrets Management

### A. Secret Injection Pipeline
Hardcoded `.env` files are strictly forbidden. The flow is:
1.  DevOps engineer sets keys in **AWS Secrets Manager (ASM)**.
2.  Terraform deploys the **External Secrets Operator (ESO)** via Helm.
3.  ESO authenticates via **IRSA (IAM Roles for Service Accounts)**.
4.  ESO automatically pulls ASM values and generates the K8s `openq-secrets` object.
5.  Pods consume secrets via `secretKeyRef` in their deployment YAMLs.

### B. Required IAM Roles (IRSA)
Terraform must generate OpenID Connect (OIDC) roles for:
1.  `aws-load-balancer-controller` (To provision ALBs).
2.  `external-secrets-operator` (To read ASM).
3.  `openq-worker-role` (Optional: If workers need direct S3/Textract access in the future).

---

## 🌐 5. Networking & Traffic Routing

### A. AWS Load Balancer Controller
Instead of declaring an `aws_lb` manually in Terraform, the infrastructure relies on the AWS Load Balancer Controller (deployed via Helm in `main.tf`). 
When `06-ingress/alb-ingress.yaml` is applied:
1.  The Controller detects the `Ingress` resource.
2.  It provisions an Application Load Balancer (ALB).
3.  It attaches the ACM Wildcard Certificate for SSL Termination.
4.  It configures Target Groups to point directly to Pod IPs.

### B. Health Probes
Every Deployment in `03-core-apps` and `04-workers` is armed with `livenessProbe` and `readinessProbe`. 
*   **API/Frontend:** HTTP `/health` pings.
*   **Celery Workers:** `celery -A app.worker status` commands.
This ensures the ALB never routes traffic to a dead pod, and Kubernetes automatically restarts frozen workers.

---

## ✅ Terraform Execution Checklist

Before running `terraform apply`, the DevOps engineer must verify:
- [ ] `variables.tf` is populated with the correct `aws_region` and `domain_name`.
- [ ] The Route 53 Hosted Zone for `domain_name` exists.
- [ ] An ACM Certificate for `*.domain_name` is validated in `us-east-1`.
- [ ] AWS Secrets Manager contains the required secret block (NEO4J_PASSWORD, OPENROUTER_API_KEY, etc.).
- [ ] `main.tf` contains the Helm releases for `aws-load-balancer-controller` and `external-secrets`.

*Designed by the OpenQ Architecture Team.*
