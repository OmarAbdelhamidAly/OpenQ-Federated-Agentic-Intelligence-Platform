<div align="center">

# 🏛️ OpenQ Cloud-Native Kubernetes Architecture
**Solution Architect Runbook: Transitioning from Docker Compose to Production K8s**

</div>

---

## 📖 Executive Summary

This guide is designed for **DevOps Engineers, SREs, and System Architects**. It serves as the definitive reference for how the local `docker-compose.yml` architecture translates into a production-grade, highly available Kubernetes (EKS) environment. 

The goal of this directory (`E:\finalproject\k8s`) is to provide a fault-tolerant, scalable, and secure deployment strategy that bridges the gap between our local 26-container Compose stack and the AWS Terraform infrastructure.

---

## 🔄 1. The Translation: Docker Compose ➔ Kubernetes

To understand the Kubernetes manifests, we must first map the concepts from our local `docker-compose.yml`:

| Docker Compose Concept | Kubernetes Equivalent | Implementation Notes |
|---|---|---|
| `services` | `Deployment` / `StatefulSet` | Stateless services (API, Workers) become Deployments. Stateful services (Postgres, Qdrant) become StatefulSets. |
| `restart: unless-stopped` | `ReplicaSet` + `LivenessProbes` | K8s naturally restarts failed Pods. We add Liveness Probes (`/health` or `celery status`) to ensure traffic never hits a dead Pod. |
| `depends_on` | `InitContainers` | Since K8s starts Pods concurrently, we use `initContainers` with `pg_isready` or `redis-cli ping` to block the API/Workers until the databases are up. |
| `networks: backend-net` | `Service` (ClusterIP) + `CoreDNS` | Containers communicate via K8s Services. Example: `http://analyst-api` in Compose becomes `http://api-service.openq-core.svc.cluster.local`. |
| `ports: "8002:8002"` | `Ingress` + `LoadBalancer` | We do NOT expose NodePorts. Instead, an AWS Application Load Balancer (ALB) routes traffic securely into the cluster based on URL paths (`/api`, `/corporate`). |
| `volumes: tenant_uploads` | `PersistentVolumeClaim` (PVC) | See the "Storage Architecture" section below for how we handle `ReadWriteMany` volumes across multiple nodes. |
| `.env` file | `ConfigMap` & `Secret` | Environment variables are injected. Secrets are managed by External Secrets Operator (ESO) syncing from AWS Secrets Manager. |

---

## 📂 2. Directory Breakdown & YAML Glossary

لتبسيط المعمارية، تم تقسيم ملفات הـ YAML إلى 7 مجلدات متتالية يجب تطبيقها بالترتيب. إليك شرح وظيفة كل ملف:

### `00-namespaces/` (البيئة المنعزلة)
*   **`01-namespaces.yaml`**: ينشئ بيئتين منفصلتين (`openq-core` للـ APIs الأساسية، و `openq-workers` للـ AI Workers الثقيلة) لضمان عدم استهلاك الـ Workers لكل مساحة הـ Cluster.

### `01-config/` (الإعدادات والأسرار)
*   **`02-config.yaml`**: يحتوي على `ConfigMap` (للمتغيرات غير السرية مثل اسم البيئة) و `Secret` وهمي. في بيئة الإنتاج، يتم تعبئة الـ Secret تلقائياً عبر External Secrets Operator (ESO) من AWS.

### `02-data-layer/` (قواعد البيانات - Staging Only)
*تُستخدم هذه الملفات للتطوير المحلي فقط، وفي AWS يجب استبدالها بخدمات مُدارة (Managed Services).*
*   **`postgres.yaml`**: قاعدة البيانات الرئيسية (Metadata).
*   **`redis.yaml`**: الـ Broker الخاص بـ Celery والمسؤول عن طوابير الانتظار.
*   **`qdrant.yaml`**: قاعدة البيانات المتجهية (Vector DB) للبحث الدلالي.
*   **`neo4j.yaml`**: الرسم البياني المعرفي (Knowledge Graph) للـ GraphRAG.
*   **`mongodb.yaml`**: لتخزين مستندات הـ JSON قبل هيكلتها.

### `03-core-apps/` (التطبيقات الأساسية)
*   **`api-gateway.yaml`**: بوابة الـ FastAPI التي تستقبل طلبات المستخدمين وتحولها لـ Celery.
*   **`corporate.yaml`**: خدمة إدارة الهيكل التنظيمي (Org-Tree).
*   **`frontend.yaml`**: واجهة المستخدم (React/Vite).

### `04-workers/` (المهام الثقيلة - Execution Pillars)
*يحتوي كل ملف هنا على `Deployment` يقوم بتشغيل Celery Worker مخصص لمهمة معينة.*
*   **`exporter-governance.yaml`**: يحتوي على 2 Deployments (واحد لتصدير الملفات `exporter` وواحد لتطبيق السياسات الأمنية `governance`).
*   **`worker-audio.yaml`**: يحلل الملفات الصوتية.
*   **`worker-code.yaml`**: يقوم بتحليل الأكواد البرمجية (ASTs) وربطها بـ Neo4j.
*   **`worker-json.yaml`**: يتعامل مع البيانات المهيكلة.
*   **`worker-pdf.yaml`**: يحتوي على 2 Deployments (واحد لـ `indexing` لرفع الملفات، وواحد لـ `analysis` للرد على الأسئلة).
*   **`worker-sql.yaml`**: يتصل بقواعد البيانات ويُنشئ استعلامات SQL.
*   **`worker-nexus.yaml`**: الـ Orchestrator الذي يربط نتائج كل הـ Workers ببعضها (Federated Search).
*   **`worker-vision.yaml`**: يعالج الفريمات المستخرجة من الكاميرات أو الفيديوهات المباشرة.

### `05-autoscaling/` (التوسع التلقائي)
*   **`hpa-api.yaml`**: يُراقب استهلاك الـ CPU للـ API ويزيد النسخ (Replicas) إذا زاد الضغط.
*   **`hpa-workers.yaml`**: يزيد عدد نسخ الـ Workers بناءً على الحمل.

### `06-ingress/` (توجيه الشبكات)
*   **`alb-ingress.yaml`**: يوجه الترافيك القادم من الإنترنت عبر AWS Application Load Balancer إلى خدمات K8s الداخلية بناءً على الـ URL.

---

## 🚀 3. Deploying the K8s Stack (Step-by-Step)

The manifests are organized logically. They must be applied in strict order:

```bash
# 1. Logical Isolation: Create namespaces to separate core APIs from heavy workers
kubectl apply -f 00-namespaces/

# 2. Configuration & Secrets: Inject ConfigMaps (Secrets handled by ESO in Prod)
kubectl apply -f 01-config/

# 3. Data Layer: Deploy Postgres, Redis, Neo4j, Qdrant (For Staging/Local K8s only! In AWS Prod, use RDS/ElastiCache)
kubectl apply -f 02-data-layer/

# 4. Core Applications: API Gateway, Corporate Service, Frontend
kubectl apply -f 03-core-apps/

# 5. Execution Pillars: The Celery Workers (Audio, PDF, SQL, Nexus)
kubectl apply -f 04-workers/

# 6. Elasticity: Horizontal Pod Autoscalers (HPA)
kubectl apply -f 05-autoscaling/

# 7. Traffic Routing: AWS ALB Ingress mapping
kubectl apply -f 06-ingress/
```

---

## 🛡️ 4. Fault Tolerance & Edge Cases (Solution Architect Notes)

As a Solution Architect, the system must survive edge cases. Here is how the Kubernetes architecture prevents cascading failures:

### A. The "Pod Eviction" Problem (Graceful Shutdown)
**Risk:** When K8s scales down or a Node is pre-empted (Spot Instances), a Celery worker might be killed mid-task.
**Solution:** 
All worker deployments implement `preStop` lifecycle hooks and `SIGTERM` handling.
```yaml
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 10 && celery -A app.worker control shutdown"]
```
Additionally, tasks use `acks_late=True` in Celery. If the pod dies before the task returns success, Redis will re-queue the task to a surviving Pod.

### B. The "Thundering Herd" API Problem
**Risk:** A sudden influx of users brings down the API Gateway or database.
**Solution:**
1.  **Queue Buffering:** The API gateway is completely asynchronous. It offloads all heavy lifting to Redis queues within milliseconds.
2.  **HPA Scale-Out:** The API deployment is attached to an `HPA` targeting 70% CPU/Memory. It scales rapidly to absorb request spikes.
3.  **Connection Pooling:** Using `NullPool` in SQLAlchemy for workers prevents connection exhaustion on the Postgres database during massive Celery scale-outs.

### C. The "Out of Memory" (OOM) Kill
**Risk:** Heavy AI tasks (like Vision processing or PDF decoding) spike RAM usage, crashing the entire physical Node.
**Solution:**
Every single deployment has strict `ResourceRequests` and `ResourceLimits`.
If `worker-pdf` exceeds its 4GB memory limit, K8s OOMKills *only that specific Pod*. The task is safely retried by another worker, protecting the API and other tenants.

---

## 💾 5. Storage Architecture (EFS & Multi-Read/Write)

In `docker-compose.yml`, volumes like `tenant_uploads` and `hf_cache` are easily shared because everything runs on one machine. In K8s across multiple AWS EC2 nodes, this requires a distributed file system.

1.  **AWS EFS CSI Driver:** Terraform provisions an Amazon Elastic File System (EFS).
2.  **ReadWriteMany (RWX):** The PVCs for `tenant_uploads` and `hf_cache` are configured as `ReadWriteMany`. 
3.  **Why?** 
    - When a user uploads a PDF, the API Gateway saves it to `/tmp/tenants` (backed by EFS).
    - The task is dispatched to `worker-pdf`.
    - `worker-pdf` (which could be running on a completely different EC2 physical node) reads the exact same file from its `/tmp/tenants` mount instantly.
    - `hf_cache` shares HuggingFace models (e.g., Pyannote for Audio) across all Pods. If one Pod downloads the 5GB model, the other 50 Pods immediately have access to it, saving immense bandwidth and disk space.

---

## 🔐 6. Security Posture

- **Network Policies:** By default, pods in `openq-workers` cannot be accessed from the public internet. Only the `api-gateway` in `openq-core` receives external traffic via the ALB.
- **No Root Containers:** All Docker images (`Dockerfile.worker`, `frontend/Dockerfile`) compile and run as non-root users (`uid: 1000`).
- **Secrets Management:** We do not store base64 encoded secrets in Git. The infrastructure relies on **External Secrets Operator (ESO)** linking to AWS Secrets Manager using IAM Roles for Service Accounts (IRSA).

---

## 🏗️ 7. Moving to AWS (Terraform Readiness)

This K8s directory represents the **application layer**. To deploy this to AWS, you must first provision the **infrastructure layer** using the `terraform/` directory.

**Golden Rule of Cloud Transition:**
Do NOT apply the `02-data-layer` manifests in AWS Production. 
Instead, let Terraform provision:
- **Amazon Aurora Serverless v2** (replaces `postgres.yaml`)
- **Amazon ElastiCache** (replaces `redis.yaml`)
- **Amazon DocumentDB** (replaces `mongodb.yaml`)

Update your `01-config/` to point the URLs to these managed AWS endpoints. This ensures database high availability, automated backups, and multi-AZ failover—things Kubernetes StatefulSets struggle to guarantee without immense operational overhead.
