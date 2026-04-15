# ☁️ AWS Deployment Architecture

This diagram visualizes the infrastructure provisioned by our Terraform modules and the Kubernetes workloads deployed via our manifests.

```mermaid
flowchart TD
    %% Global styling
    classDef aws fill:#FF9900,stroke:#232F3E,stroke-width:2px,color:black,font-weight:bold;
    classDef vpc fill:#EFEFEF,stroke:#8C4FFF,stroke-width:2px,stroke-dasharray: 5 5;
    classDef subnet fill:#D5F5E3,stroke:#2ECC71,stroke-width:1px;
    classDef eks fill:#3498DB,stroke:#2980B9,stroke-width:2px,color:white;
    classDef pod fill:#E8F8F5,stroke:#1ABC9C,stroke-width:1px;
    classDef data fill:#9B59B6,stroke:#8E44AD,stroke-width:2px,color:white;

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
                        FE[Frontend SPA Pods]:::pod
                        Gov[Governance & Exporter Pods]:::pod
                    end
                    
                    subgraph NS_Workers ["Namespace: openq-workers"]
                        Workers[Pillar Celery Workers + HPA\n(SQL, CSV, PDF, Nexus, Audio, Image)]:::pod
                    end
                end
                
                subgraph DataLayer ["💾 Persistent Data Layer"]
                    direction LR
                    Aurora[(Aurora Serverless v2 PostgreSQL\n0.5 - 2.0 ACU)]:::data
                    Redis[(ElastiCache Redis cluster\nMulti-AZ)]:::data
                end
            end
        end
        
        subgraph Mgt ["🛠️ Management, Security & CI/CD"]
            ECR[Amazon ECR\n(Docker Images)]:::aws
            SecretsManager[AWS Secrets Manager\n(DB Passwords)]:::aws
            KMS[AWS KMS\n(Encryption Keys)]:::aws
            S3[(Terraform State S3)]:::aws
            Dynamo[(Terraform Locks DB)]:::aws
        end
    end

    %% Network flows
    ALB -->|/api| API
    ALB -->|/| FE
    
    %% Application flows
    API -->|Deploy Tasks| Workers
    API -->|Read/Write| Aurora
    API -->|State/Cache| Redis
    
    Workers -->|Read/Write| Aurora
    Workers -->|Checkpoints| Redis
    Gov -->|Manage Tasks| Workers
    
    %% Security & Management Links
    API -.->|Fetch Credentials| SecretsManager
    EKS -.->|Pull Images| ECR
    
    %% Encryption representations
    Aurora -.->|Encrypted At-Rest| KMS
    Redis -.->|Encrypted At-Rest| KMS
    EKS -.->|Control Plane Secrets| KMS

```

## Infrastructure Highlights

1. **High Availability**: The VPC spans multiple Data Centers (Availability Zones). The DB, Redis, and EKS nodes automatically distribute across them.
2. **Security**: All persistent data layers sit inside Private Subnets, unreachable by the public internet. Access is strictly via the Application Load Balancer.
3. **KMS Encryption**: Storage devices, database volumes, cache data, and Kubernetes secrets are secured at rest using AWS KMS.
4. **Terraform Collaboration**: Provisioning uses an isolated S3 bucket for tracking state files, secured from conflicts using DynamoDB state locking.
