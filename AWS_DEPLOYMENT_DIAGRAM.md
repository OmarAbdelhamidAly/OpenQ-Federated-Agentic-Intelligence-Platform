# ☁️ AWS Deployment Architecture

This diagram visualizes the infrastructure provisioned by our Terraform modules and the Kubernetes workloads deployed via our manifests, synchronized for the 22-service federated intelligence stack.

```mermaid
flowchart TD
    %% Global styling
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:black,font-weight:bold;
    classDef vpc fill:#EFEFEF,stroke:#8C4FFF,stroke-width:2px,stroke-dasharray: 5 5;
    classDef subnet fill:#D5F5E3,stroke:#2ECC71,stroke-width:1px;
    classDef eks fill:#3498DB,stroke:#2980B9,stroke-width:2px,color:white;
    classDef pod fill:#E8F8F5,stroke:#1ABC9C,stroke-width:1px;
    classDef data fill:#9B59B6,stroke:#8E44AD,stroke-width:2px,color:white;
    classDef obs fill:#34495E,stroke:#2C3E50,stroke-width:1px,color:white;

    %% Client entry
    Client([Internet / Client]) --> Route53
    
    %% AWS Cloud Boundaries
    subgraph AWS ["☁️ Amazon Web Services (us-east-1)"]
        direction TB
        
        Route53[Amazon Route 53]:::aws --> ALB
        
        subgraph VPC ["🔒 Virtual Private Cloud (10.0.0.0/16)"]
            direction TB
            
            subgraph PublicSubnet ["🌐 Public Subnets"]
                ALB[Application Load Balancer]:::aws
                NAT[NAT Gateway]:::aws
            end
            
            subgraph PrivateSubnet ["🛡️ Private Subnets"]
                direction TB
                
                subgraph EKS ["⚙️ Amazon EKS Cluster (openq-eks-cluster)"]
                    direction TB
                    
                    subgraph NS_Core ["Namespace: openq-core"]
                        API[API Gateway Pods + HPA]:::pod
                        Corp[Corporate Environment Service]:::pod
                        FE[Frontend SPA Pods]:::pod
                        Gov[Governance & Exporter Pods]:::pod
                    end
                    
                    subgraph NS_Workers ["Namespace: openq-workers"]
                        Workers[Pillar Celery Workers + HPA\n(SQL, CSV, JSON, PDF, Nexus, Audio, Image, Video)]:::pod
                    end
                end
                
                subgraph DataLayer ["💾 Multi-Engine Persistence Layer"]
                    direction LR
                    Aurora[(Aurora Serverless v2 PostgreSQL)]:::data
                    Redis[(ElastiCache Redis cluster)]:::data
                    Neo4j[(Neo4j Knowledge Graph)]:::data
                    Qdrant[(Qdrant Vector DB)]:::data
                    Mongo[(MongoDB Document Store)]:::data
                end
            end
        end
        
        subgraph Mgt ["🛠️ Management, Security & Observability"]
            ECR[Amazon ECR\n(Docker Images)]:::aws
            KMS[AWS KMS\n(Central Encryption)]:::aws
            S3[(Terraform State S3)]:::aws
            
            subgraph Obs ["📊 Observability Stack"]
                Prom[Prometheus]:::obs
                Graf[Grafana]:::obs
            end
        end
    end

    %% Network flows
    ALB -->|/api| API
    ALB -->|/| FE
    
    %% Application flows
    API -->|Deploy Tasks| Workers
    API -->|Read/Write| Aurora
    API -->|State/Cache| Redis
    Corp -->|Org Hierarchy| Aurora
    
    Workers -->|Relational| Aurora
    Workers -->|State/HITL| Redis
    Workers -->|Graph Entities| Neo4j
    Workers -->|Vector RAG| Qdrant
    Workers -->|Doc Metadata| Mongo
    
    Gov -->|Manage Tasks| Workers
    
    %% Security & Management Links
    EKS -.->|Pull Images| ECR
    EKS -.->|Control Plane Secrets| KMS
    DataLayer -.->|Encrypted At-Rest| KMS

```

## Infrastructure Highlights

1. **High Availability**: The VPC spans multiple Availability Zones. The Data Layer (Aurora, Redis, Neo4j) and EKS nodes automatically distribute across them for maximum resilience.
2. **Security**: All persistent data stores sit inside Private Subnets. Access is strictly via the Application Load Balancer and internal Kubernetes routing.
3. **KMS Centralized Encryption**: All storage devices, database volumes, cache data, and Kubernetes control-plane secrets are secured at-rest using a Customer Managed Key (CMK) in AWS KMS.
4. **Multi-Engine Intelligence**:
    - **PostgreSQL**: Metadata, users, and relational business data.
    - **Neo4j**: Codebase AST, entity relationships, and cross-pillar strategic forge.
    - **Qdrant**: High-dimensional vector embeddings for PDF RAG and JSON semantic search.
    - **MongoDB**: Unstructured metadata and analysis aggregation pipelines.
5. **Observability Stack**: Integrated Prometheus and Grafana for real-time monitoring of job latencies, queue depths, and cluster health.
