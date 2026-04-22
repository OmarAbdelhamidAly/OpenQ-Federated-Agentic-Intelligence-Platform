# 🏛️ OpenQ K8s Architecture Blueprint (Pre-Terraform)

This document serves as the comprehensive architectural blueprint for the OpenQ Kubernetes environment. It is designed specifically as a reference guide for DevOps engineers and System Architects writing the Terraform infrastructure-as-code (IaC).

---

## 1. Directory Structure (Separation of Concerns)

The Kubernetes manifests have been restructured to strictly separate stateful data components from stateless application code, ensuring modularity and easier CI/CD pipelines.

```text
k8s/
├── 00-namespaces/     # Logical isolation (openq-core, openq-workers) + ResourceQuotas
├── 01-config/         # ConfigMaps (openq-config) + Secrets placeholders (openq-secrets)
├── 02-data-layer/     # StatefulSets with PVCs (Redis, Neo4j, Qdrant, MongoDB)
├── 03-core-apps/      # Stateless Endpoints (API Gateway, Frontend, Corporate)
├── 04-workers/        # Celery Workers (SQL, Code, JSON, PDF, Nexus, Audio, Governance, Exporter)
├── 05-autoscaling/    # HorizontalPodAutoscalers (HPAs) for traffic bursts
└── 06-ingress/        # AWS ALB Ingress Controller rules (HTTPS/TLS)
```

---

## 2. Infrastructure Requirements (Terraform Targets)

To support this architecture in production, the Terraform code MUST provision the following AWS components:

### A. Compute (AWS EKS)
*   **Cluster**: EKS v1.28+
*   **Node Groups (Recommended)**:
    *   **`core-nodes`**: `t3.medium` or `m5.large` for API, Frontend, and Data Layer.
    *   **`worker-nodes`**: `c5.2xlarge` or `m5.2xlarge` for heavy CPU workloads (PDF parsing, Cypher queries).
*   **Node Autoscaling**: Provision **Karpenter** or **Cluster Autoscaler** to dynamically spin up nodes when HPAs trigger scaling.

### B. Managed Services (Replacing Local K8s Data Layer)
While `02-data-layer` provides local K8s manifests for Redis/MongoDB/Neo4j/Qdrant, **Production Terraform** should optionally replace them with managed equivalents for maximum resilience:
*   **PostgreSQL**: Amazon Aurora Serverless v2 (PostgreSQL compatible).
*   **Redis**: Amazon ElastiCache (Redis OSS).
*   **MongoDB**: Amazon DocumentDB (Elastic Clusters).

### C. Identity & Security (IAM & IRSA)
*   **AWS Secrets Manager (ASM)**: Store `OPENROUTER_API_KEY`, `NEO4J_PASSWORD`, `DATABASE_URL`, etc.
*   **External Secrets Operator (ESO)**: Provision ESO via Helm in Terraform to automatically sync ASM secrets into the `openq-secrets` K8s Secret.
*   **IAM Roles for Service Accounts (IRSA)**:
    *   Role for **AWS Load Balancer Controller**.
    *   Role for **External Secrets**.
    *   Role for Workers needing S3 access (if tenant uploads move from EFS to S3).

---

## 3. Storage Strategy (Volumes & PVCs)

### A. Block Storage (EBS / gp3)
Used strictly for the `02-data-layer` StatefulSets.
*   **StorageClass**: `gp3` (Ensure the AWS EBS CSI driver is provisioned via Terraform).
*   **Allocations**: Neo4j (20Gi), Qdrant (30Gi), Redis (10Gi), MongoDB (20Gi).

### B. Shared File Systems (EFS)
The architecture heavily relies on shared file systems for AI caching and tenant document processing. Terraform MUST provision an **AWS EFS** file system and the **EFS CSI Driver**.
*   **`hf_cache`**: Shared `PersistentVolumeClaim` (backed by EFS) mounted on PDF workers to prevent redundant HuggingFace model downloads.
*   **`tenant-data`**: Currently mapped as `emptyDir`. **Must be upgraded to an EFS PVC** so all workers (JSON, SQL, Audio, PDF) can access uploaded files concurrently.

---

## 4. Autoscaling Strategy

*   **Horizontal Pod Autoscalers (HPAs)**: Configured in `05-autoscaling`. Targets 70% CPU utilization.
*   **Worker Limits**: PDF Analysis/Indexing workers require high memory (`14Gi` limits, `4Gi` requests). EKS Node groups must be sized accordingly to prevent `OOMKilled` errors during horizontal scaling.

---

## 5. Networking & Ingress

*   **AWS Load Balancer Controller**: Terraform must deploy the ALB controller via Helm.
*   **Certificate Manager (ACM)**: Terraform must issue a TLS wildcard certificate (e.g., `*.openq.com`) and output the `certificate_arn`.
*   **Ingress Rules**: `06-ingress/alb-ingress.yaml` expects the ACM ARN to terminate SSL. HTTP traffic is automatically redirected to HTTPS. 

---

## 6. Future Architectural Recommendations (Post-Terraform)
1.  **Network Policies**: Implement strict `NetworkPolicy` manifests to ensure that `openq-workers` can only communicate with the `02-data-layer` and the OpenRouter API, preventing any direct external inbound traffic.
2.  **Pod Disruption Budgets (PDBs)**: Add PDBs for the `api-gateway` and `frontend` to ensure at least 1 replica is always available during Node draining/upgrades.
3.  **S3 Migration**: Consider migrating `tenant_uploads` from EFS to S3 (using `boto3` in the Celery workers) to drastically reduce storage costs for large audio/PDF files.
