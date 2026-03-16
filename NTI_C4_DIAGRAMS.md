# C4 Architecture Diagrams

**DataAnalyst.AI — Autonomous Enterprise Data Analyst**

---

## Level 1 — System Context

Who uses the system and what external systems does it interact with?

```mermaid
graph TB
    Admin["👨‍💼 Admin User<br/>Manages tenant, uploads data<br/>approves SQL queries, sets policies"]
    Viewer["👤 Analyst / Viewer<br/>Asks questions, views insights<br/>exports reports"]
    DevOps["👨‍💻 DevOps Engineer<br/>Deploys and monitors<br/>the platform"]

    System["🤖 DataAnalyst.AI<br/>Autonomous multi-tenant SaaS platform<br/>Turns raw data into executive insights<br/>via multi-agent LangGraph pipelines"]

    Groq["☁️ Groq API<br/>LLM inference<br/>Llama-3.1-8B + 3.3-70B"]
    UserDB["🗄️ User's Database<br/>PostgreSQL / MySQL<br/>Enterprise data source"]

    Admin  -->|"HTTPS — manage, approve, configure"| System
    Viewer -->|"HTTPS — query, view, export"| System
    DevOps -->|"Docker / K8s / CLI"| System
    System -->|"LLM completions"| Groq
    System -->|"Read-only SELECT queries"| UserDB

    style System fill:#1F3864,color:#fff,stroke:#2E5B8A
    style Groq   fill:#2E5B8A,color:#fff,stroke:#4472C4
    style UserDB fill:#2E5B8A,color:#fff,stroke:#4472C4
    style Admin  fill:#D5E8F0,color:#1F3864,stroke:#2E5B8A
    style Viewer fill:#D5E8F0,color:#1F3864,stroke:#2E5B8A
    style DevOps fill:#D5E8F0,color:#1F3864,stroke:#2E5B8A
```

---

## Level 2 — Container Diagram

What are the deployable units and how do they communicate?

```mermaid
graph TB
    User["👤 User / Admin"]

    subgraph Docker ["🐳 Docker Compose Network"]
        UI["🖥️ Glassmorphism SPA<br/>Vanilla JS + Plotly.js<br/>Served from api/app/static/"]

        API["🔀 API Gateway<br/>FastAPI · asyncpg · :8002<br/>JWT auth · AES-256 encryption<br/>Rate limiting · Security headers"]

        subgraph Workers ["⚙️ Celery Workers"]
            Gov["🛡️ Governance<br/>queue: governance<br/>intake + guardrail agents"]
            SQL["🗃️ worker-sql<br/>queue: pillar.sql<br/>11-node LangGraph pipeline"]
            CSV["📊 worker-csv<br/>queue: pillar.csv<br/>7-node LangGraph pipeline"]
            Other["📄 worker-json<br/>worker-pdf<br/>exporter"]
        end

        subgraph Storage ["💾 Storage Layer"]
            PG["PostgreSQL :5433<br/>Tenants · Users · Jobs<br/>Results · Policies"]
            Redis["Redis :6379<br/>Celery broker<br/>JWT blacklist<br/>LangGraph checkpoints"]
            Qdrant["Qdrant :6333<br/>PDF vector store<br/>ColPali multi-vector"]
            Vol["Shared Volume<br/>Uploaded files<br/>Exported reports"]
        end
    end

    Groq["☁️ Groq API"]

    User   -->|"HTTPS"| UI
    User   -->|"REST"| API
    UI     -->|"fetch"| API
    API    -->|"Celery task"| Redis
    Redis  -->|"task dispatch"| Gov
    Gov    -->|"Celery task"| Redis
    Redis  -->|"task dispatch"| SQL
    Redis  -->|"task dispatch"| CSV
    Redis  -->|"task dispatch"| Other
    API    -->|"asyncpg"| PG
    SQL    -->|"asyncpg"| PG
    CSV    -->|"asyncpg"| PG
    SQL    -->|"LangGraph state"| Redis
    SQL    -->|"HTTPS"| Groq
    CSV    -->|"HTTPS"| Groq
    Gov    -->|"HTTPS"| Groq
    SQL    -->|"vectors"| Qdrant
    API    -->|"file I/O"| Vol

    style API   fill:#1F3864,color:#fff,stroke:#2E5B8A
    style SQL   fill:#1F3864,color:#fff,stroke:#2E5B8A
    style CSV   fill:#1F3864,color:#fff,stroke:#2E5B8A
    style Gov   fill:#C55A11,color:#fff,stroke:#843C0C
    style Groq  fill:#2E5B8A,color:#fff,stroke:#4472C4
    style Redis fill:#DC382D,color:#fff,stroke:#9E1C1C
    style PG    fill:#336791,color:#fff,stroke:#1F4060
    style Qdrant fill:#2E5B8A,color:#fff,stroke:#4472C4
```

---

## Level 3 — Component Diagram: API Gateway

```mermaid
graph TB
    Client["👤 Client"]

    subgraph API ["🔀 services/api — FastAPI Gateway :8002"]
        Main["app/main.py<br/>App factory + self-healing<br/>DB migration on startup"]

        subgraph Routers ["📡 Routers"]
            Auth["routers/auth.py<br/>register · login · refresh · logout<br/>JWT rotation + Redis revocation"]
            DS["routers/data_sources.py<br/>upload CSV/XLSX/SQLite<br/>connect SQL (AES-256 encrypted)<br/>auto schema profiling"]
            Analysis["routers/analysis.py<br/>submit query · poll status<br/>approve HITL · fetch result"]
            Other["routers/users.py<br/>routers/knowledge.py<br/>routers/policies.py<br/>routers/metrics.py<br/>routers/reports.py"]
        end

        subgraph Infra ["🔒 Infrastructure"]
            Sec["security.py<br/>JWT access (30min)<br/>JWT refresh (7 days)<br/>bcrypt passwords"]
            Guard["sql_guard.py<br/>Layer 1: SELECT-only<br/>Layer 2: keyword blocklist<br/>Layer 3: LLM policy"]
            MW["middleware.py<br/>CORS · rate limiting<br/>security headers<br/>request logging"]
            Enc["adapters/encryption.py<br/>AES-256-GCM<br/>SQL credential encryption"]
            BL["token_blacklist.py<br/>Redis JTI revocation<br/>instant logout enforcement"]
        end

        Worker["app/worker.py<br/>Celery task definitions<br/>governance_task · pillar_task"]
    end

    PG["PostgreSQL"]
    Redis["Redis"]

    Client --> Auth & DS & Analysis & Other
    Main --> Routers
    Auth --> Sec & BL
    DS --> Enc
    Analysis --> Guard & Worker
    Worker -->|"Celery"| Redis
    Routers -->|"asyncpg"| PG

    style Auth     fill:#1F3864,color:#fff,stroke:#2E5B8A
    style Guard    fill:#C55A11,color:#fff,stroke:#843C0C
    style Enc      fill:#C55A11,color:#fff,stroke:#843C0C
    style BL       fill:#C55A11,color:#fff,stroke:#843C0C
```

---

## Level 3 — Component Diagram: SQL Worker

```mermaid
graph TB
    subgraph SQLWorker ["🗃️ services/worker-sql — LangGraph SQL Pipeline"]
        subgraph Graph ["🔄 modules/sql/workflow.py"]
            DD["data_discovery<br/>Schema compression<br/>FK inference<br/>ERD generation"]
            AG["analysis_generator<br/>ReAct agent<br/>Golden SQL examples<br/>ANSI SELECT generation"]
            HA["human_approval<br/>HITL interrupt<br/>Redis checkpoint"]
            EX["execution<br/>Run approved SQL<br/>Zero-row reflection"]
            BT["backtrack<br/>Failure analysis<br/>Hint injection"]
            HF["hybrid_fusion<br/>Qdrant KB context<br/>PDF knowledge enrichment"]
            VIZ["visualization<br/>Plotly chart JSON<br/>Auto chart type selection"]
            INS["insight<br/>Executive summary<br/>Data-grounded narrative"]
            VER["verifier<br/>Quality gate<br/>Insight vs data check"]
            REC["recommendation<br/>3 actionable next steps"]
            MEM["memory_persistence<br/>Save to insight_memory<br/>Golden SQL examples"]
            OA["output_assembler<br/>Final JSON result<br/>DB persistence"]
        end

        subgraph Tools ["🔧 Tools"]
            RunSQL["run_sql_query<br/>Async DB execution<br/>1000 row limit"]
            SSD["sql_schema_discovery<br/>Table profiling<br/>Sample values"]
        end

        subgraph Utils ["📚 Utils"]
            GS["golden_sql<br/>Few-shot SQL examples"]
            IM["insight_memory<br/>Successful analysis cache"]
            SM["schema_mapper<br/>Column type normalization"]
            SS["schema_selector<br/>Token-budget schema compression"]
            SV["sql_validator<br/>EXPLAIN cost analysis"]
        end
    end

    DD --> AG --> HA --> EX
    EX -->|"0 rows"| BT --> AG
    EX -->|"success"| HF --> VIZ --> INS --> VER --> REC --> MEM --> OA
    AG --> RunSQL & SSD
    AG --> GS & SS & SM
    VER --> SV
    MEM --> IM

    style AG  fill:#1F3864,color:#fff,stroke:#2E5B8A
    style HA  fill:#C55A11,color:#fff,stroke:#843C0C
    style BT  fill:#C55A11,color:#fff,stroke:#843C0C
    style EX  fill:#375623,color:#fff,stroke:#255E1E
```

---

## Level 3 — Component Diagram: Governance Worker

```mermaid
graph TB
    subgraph Gov ["🛡️ services/governance — Policy Enforcement"]
        subgraph GovGraph ["🔄 modules/governance/workflow.py"]
            IA["intake_agent<br/>Classify intent<br/>Extract entities<br/>Detect ambiguity"]
            GA["guardrail_agent<br/>Check admin policies<br/>PII detection<br/>LLM-based evaluation"]
        end

        Policies["Admin-defined rules<br/>e.g. never expose salary data<br/>never query audit logs"]
    end

    Redis["Redis — receives governance task"]
    Pillar["Redis — dispatches to pillar queue"]

    Redis --> IA
    IA -->|"clarification needed"| Done["Job: awaiting_clarification"]
    IA --> GA
    GA --> Policies
    GA -->|"policy violation"| Reject["Job: error (policy blocked)"]
    GA -->|"approved"| Pillar

    style GA   fill:#C55A11,color:#fff,stroke:#843C0C
    style Reject fill:#A32D2D,color:#fff,stroke:#701F1F
    style Done fill:#2E5B8A,color:#fff,stroke:#4472C4
```

---

## Level 4 — Code: Key Classes

```mermaid
classDiagram
    class AnalysisJob {
        +UUID id
        +UUID tenant_id
        +UUID user_id
        +UUID source_id
        +str question
        +str intent
        +str status
        +str generated_sql
        +list thinking_steps
        +int complexity_index
        +int retry_count
        +UUID kb_id
    }

    class DataSource {
        +UUID id
        +UUID tenant_id
        +str type
        +str name
        +str file_path
        +str config_encrypted
        +dict schema_json
        +str auto_analysis_status
        +dict auto_analysis_json
        +str domain_type
    }

    class Tenant {
        +UUID id
        +str name
        +str plan
    }

    class User {
        +UUID id
        +UUID tenant_id
        +str email
        +str password_hash
        +str role
    }

    class AnalysisState {
        +str question
        +str source_id
        +str connection_string
        +dict schema_summary
        +str generated_sql
        +dict analysis_results
        +list charts
        +str insight_report
        +list recommendations
        +str reflection_context
        +int reflection_count
        +int retry_count
        +bool approval_granted
    }

    class Settings {
        +str ENV
        +str DATABASE_URL
        +str REDIS_URL
        +str SECRET_KEY
        +str AES_KEY
        +str GROQ_API_KEY
        +str LLM_MODEL
        +validate_production_secrets()
    }

    Tenant "1" --> "many" User : has
    Tenant "1" --> "many" DataSource : owns
    User "1" --> "many" AnalysisJob : submits
    DataSource "1" --> "many" AnalysisJob : analyzed by
    AnalysisJob --> AnalysisState : creates state
```

---

## LangGraph SQL Pipeline Flow

```mermaid
flowchart TD
    Start([Job dispatched to worker-sql]) --> DD

    DD["data_discovery<br/>Schema compression + FK inference + ERD"]
    AG["analysis_generator<br/>ReAct: SQL generation with golden examples"]
    HA["human_approval<br/>HITL INTERRUPT — Redis checkpoint"]
    EX["execution<br/>Run SQL against live database"]
    BT["backtrack<br/>Analyze failure + inject hint"]
    HF["hybrid_fusion<br/>Fetch Qdrant PDF context"]
    VIZ["visualization<br/>Generate Plotly charts"]
    INS["insight<br/>Executive summary"]
    VER["verifier<br/>Quality gate"]
    REC["recommendation<br/>3 action items"]
    MEM["memory_persistence<br/>Save to insight memory"]
    OA["output_assembler<br/>Save result to PostgreSQL"]
    End([Job status: done])

    DD --> AG

    AG -->|"user_id = auto_analysis\nOR approval_granted = True"| EX
    AG -->|"normal user"| HA
    HA -->|"Admin approves via UI"| EX

    EX -->|"row_count = 0\nreflection_count < 1"| BT
    BT -->|"inject case hint\nincrement retry"| AG
    EX -->|"success"| HF

    HF --> VIZ --> INS --> VER --> REC --> MEM --> OA --> End

    style AG  fill:#1F3864,color:#fff,stroke:#2E5B8A
    style HA  fill:#C55A11,color:#fff,stroke:#843C0C
    style BT  fill:#C55A11,color:#fff,stroke:#843C0C
    style EX  fill:#375623,color:#fff,stroke:#255E1E
    style End fill:#375623,color:#fff,stroke:#255E1E
```

---

## CSV Pipeline Flow

```mermaid
flowchart TD
    Start([Job dispatched to worker-csv]) --> DD

    DD["data_discovery<br/>Profile DataFrame: dtypes, nulls,<br/>uniques, quality score"]
    DC["data_cleaning<br/>Null imputation, type coercion,<br/>outlier flagging"]
    AN["analysis<br/>Pandas query execution<br/>Statistical analysis"]
    VIZ["visualization<br/>Plotly charts"]
    INS["insight<br/>Executive summary"]
    REC["recommendation<br/>Action items"]
    OA["output_assembler<br/>Final result"]
    End([Job status: done])

    DD -->|"quality_score < 0.9"| DC
    DD -->|"quality_score >= 0.9"| AN
    DC --> AN
    AN --> VIZ --> INS --> REC --> OA --> End

    style AN  fill:#1F3864,color:#fff,stroke:#2E5B8A
    style DC  fill:#C55A11,color:#fff,stroke:#843C0C
    style End fill:#375623,color:#fff,stroke:#255E1E
```

---

## Security Architecture

```mermaid
graph TB
    subgraph Auth ["🔐 JWT Authentication Flow"]
        Login["POST /auth/login"] -->|"access_token 30min<br/>refresh_token 7 days"| Client
        Client -->|"Authorization: Bearer"| Protected["Protected Endpoint"]
        Protected --> Verify["Verify signature<br/>Check expiry<br/>Extract tenant_id + role"]
        Expired["Token expired"] -->|"POST /auth/refresh"| Rotate["Revoke old JTI<br/>Issue new token pair"]
        Logout["POST /auth/logout"] --> Revoke["Delete JTI from Redis<br/>Token dead immediately"]
    end

    subgraph Guard ["🛡️ SQL Security Layers"]
        L1["Layer 1: Regex<br/>SELECT or WITH only<br/>No DROP DELETE INSERT..."]
        L2["Layer 2: Keyword scan<br/>TRUNCATE EXEC GRANT...<br/>Anywhere in query"]
        L3["Layer 3: LLM Guardrail<br/>Admin policy enforcement<br/>PII semantic detection"]
        L1 --> L2 --> L3 -->|"approved"| Execute["Execute against DB"]
        L1 -->|"blocked"| Reject1["ValueError: not SELECT"]
        L2 -->|"blocked"| Reject2["ValueError: forbidden keyword"]
        L3 -->|"blocked"| Reject3["Policy violation: job rejected"]
    end

    style L1 fill:#C55A11,color:#fff
    style L2 fill:#C55A11,color:#fff
    style L3 fill:#A32D2D,color:#fff
    style Execute fill:#375623,color:#fff
    style Reject1 fill:#A32D2D,color:#fff
    style Reject2 fill:#A32D2D,color:#fff
    style Reject3 fill:#A32D2D,color:#fff
```
