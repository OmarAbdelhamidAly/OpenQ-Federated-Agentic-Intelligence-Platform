# 🚀 OpenQ: Distributed Federated Agentic Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/release/python-3100/)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-EKS-blue)](https://aws.amazon.com/eks/)
[![Terraform](https://img.shields.io/badge/Infrastructure-Terraform-purple)](https://www.terraform.io/)

OpenQ is an enterprise-grade autonomous intelligence platform that bridges the gap between **Developer Intelligence** and **Business Strategy**. It orchestrates a distributed multi-agent system to provide unified, cross-pillar reasoning across heterogeneous data sources including Codebases, SQL Databases, Multi-modal Documents, and Multimedia.

> [!IMPORTANT]
> This platform is a mix between **Amazon Q Developer** and **Amazon Q Business**, designed to understand not just the data, but the "Why" behind it across fragmented enterprise ecosystems.

---

## 🏛️ Architecture Overview

The platform is built on a **Decoupled Federated Architecture** consisting of 22 microservices, independent scaling, and fault-tolerant asynchronous execution.

### 🛡️ 1. Governance & Gateway
- **API Gateway (FastAPI):** High-throughput entry point for multi-tenant requests.
- **Intent Classification:** Real-time analysis of user goals (Trend/Ranking/Anomaly/Chat).
- **PII Redaction:** Automated data masking and policy enforcement before data reaches analytical nodes.

### 🧠 2. The 9 Specialist Workers (Intelligence Pillars)
Every worker is a specialized agentic node with its own state-machine logic:
- **Worker-SQL:** 11-node self-healing loop for schema discovery and Golden-SQL generation.
- **Worker-PDF:** Multi-pathway synthesis (Deep Vision vs. Fast Text vs. Hybrid OCR).
- **Worker-Code:** Strategic developer assistant using AST parsing and Neo4j graph linkage.
- **Worker-Nexus:** The **Federation Layer** performing cross-pillar reasoning across all modalities via Text-to-Cypher graph queries.
- **Worker-Media:** Vision-based (Gemini 1.5 Flash) analysis of Image, Audio, and Video.
- **Worker-JSON/CSV:** High-performance tabular data intelligence.

---

## 🏗️ Engineering Principles

### Clean Architecture & DDD
Every service follows the **Hexagonal Architecture (Ports & Adapters)** pattern to enforce strict Dependency Inversion (DIP):
- **Domain Layer:** Pure business logic and LangGraph state definitions decoupled from infrastructure.
- **Application Layer:** Orchestrates multi-agent use cases (Ingestion, Retrieval, Synthesis).
- **Infrastructure Layer:** Swappable adapters for LLMs (OpenRouter/Bedrock/Ollama) and DB providers (Qdrant/Neo4j).

### Robust Agentic Loops
- **Self-Healing:** Built-in verification loops to cross-check model outputs against raw source context.
- **Episodic Memory:** Persistent conversation state across multi-turn complex sessions.
- **Anti-Hallucination:** Cyclic LangGraph nodes for remediation of failed verification passes.

---

## ☁️ Cloud-Native Stack

### Infrastructure as Code (IaC)
- **Terraform:** Automated provisioning of AWS EKS, Aurora Serverless v2, ElastiCache, and ECR.
- **Kubernetes:** Managed via manifests with **Horizontal Pod Autoscaling (HPA)** and resource-boundary enforcement.

### DevOps & Observability
- **CI/CD:** Automated GitHub Actions pipeline for secure image building and rolling updates.
- **Observability:** Prometheus & Grafana stack tracking **p50/p95/p99 latency** across the entire service mesh.
- **Queue Monitoring:** Real-time task tracking via Celery Flower.

---

## 🚦 Getting Started (Local Development)

### Prerequisites
- Docker & Docker Compose
- Python 3.10+
- OpenRouter API Key (or Gemini API Key)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/OmarAbdelhamidAly/OpenQ-Federated-Agentic-Intelligence-Platform.git
   cd OpenQ
   ```
2. Setup environment:
   ```bash
   cp .env.example .env
   # Fill in your API keys and database credentials
   ```
3. Boot the platform:
   ```bash
   docker-compose up -d --build
   ```

---

## 🛰️ Tech Stack
- **Frameworks:** LangGraph, LangChain, FastAPI, Celery.
- **Vector DB:** Qdrant.
- **Graph DB:** Neo4j.
- **Deployment:** Kubernetes (EKS), Terraform, Docker.
- **Models:** Gemini 2.0 Flash, Llama 3.3, Claude 3.5 Sonnet.

---

Built with ❤️ by **Omar Abdelhamid Aly**.
For full architectural documentation, see [NTI_ARCHITECTURE.md](./NTI_ARCHITECTURE.md).
