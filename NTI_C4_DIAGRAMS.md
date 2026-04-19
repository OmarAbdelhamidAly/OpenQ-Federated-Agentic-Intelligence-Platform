# C4 Architecture Diagrams

**OpenQ — Autonomous Multi-Pillar Enterprise Data Intelligence Platform**

> C4 Model: four levels of zoom — Context → Container → Component → Code.
> Each diagram narrows scope. Start at Level 1 for the big picture.

---

## Level 1 — System Context

*Who uses the system, and what external systems does it interact with?*

```mermaid
graph TB
    Admin["👨‍💼 Admin User
    Connects data sources, approves
    SQL queries, sets guardrail policies,
    manages tenant users & groups"]

    Viewer["👤 Analyst / Viewer
    Asks natural-language questions,
    views charts & insights,
    exports reports via voice or text"]

    DevOps["👨‍💻 DevOps Engineer
    Deploys, monitors, and
    scales the platform via
    Docker Compose / Kubernetes"]

    System["🤖 OpenQ
    Autonomous multi-tenant SaaS platform.
    Turns raw multi-modal data into
    executive insights via 22 microservices
    orchestrated by LangGraph agents.
    Supports CSV, SQL, JSON, PDF,
    Code, Audio, Image, Video."]

    OpenRouter["☁️ OpenRouter API
    Primary LLM gateway
    google/gemini-2.0-flash-001"]

    Groq["☁️ Groq API
    LLM fallback
    Llama-3.3-70B / 3.1-8B"]

    Gemini["☁️ Google Gemini API
    Direct fallback + PDF/Image/Video Vision
    gemini-2.0-flash-exp"]

    UserDB["🗄️ User's Database
    PostgreSQL / MySQL
    Enterprise data source"]

    Qdrant["🔍 Qdrant Cloud
    Vector database
    JSON RAG & PDF embeddings"]

    Neo4j["🕸️ Neo4j
    Knowledge Graph
    Code AST + cross-pillar entities"]

    Admin  -->|"HTTPS — manage, approve, configure"| System
    Viewer -->|"HTTPS — query, view, export, voice"| System
    DevOps -->|"Docker / K8s / Prometheus"| System
    System -->|"LLM completions — primary"| OpenRouter
    System -->|"LLM completions — fallback 1"| Groq
    System -->|"Vision + LLM — fallback 2"| Gemini
    System -->|"Read-only SELECT queries"| UserDB
    System -->|"Vector upsert + search"| Qdrant
    System -->|"Graph write + Cypher query"| Neo4j

    style System fill:#1F3864,color:#fff,stroke:#2E5B8A
    style OpenRouter fill:#2E5B8A,color:#fff,stroke:#4472C4
    style Groq fill:#2E5B8A,color:#fff,stroke:#4472C4
    style Gemini fill:#4285F4,color:#fff,stroke:#2E5B8A
    style UserDB fill:#2E5B8A,color:#fff,stroke:#4472C4
    style Qdrant fill:#4F46E5,color:#fff,stroke:#4472C4
    style Neo4j fill:#018BFF,color:#fff,stroke:#0066CC
    style Admin  fill:#D5E8F0,color:#1F3864,stroke:#2E5B8A
    style Viewer fill:#D5E8F0,color:#1F3864,stroke:#2E5B8A
    style DevOps fill:#D5E8F0,color:#1F3864,stroke:#2E5B8A
```

---

## Level 2 — Container Diagram

*What are the deployable units, and how do they communicate?*

```mermaid
graph TB
    User["👤 User / Admin"]

    subgraph Docker ["🐳 Docker Compose Network (22 services)"]
        UI["🖥️ Glassmorphism SPA
        Vanilla JS + ECharts/Plotly
        Served from api/app/static/"]

        ReactUI["⚛️ React + TypeScript SPA
        Vite · Component-based UI
        ECharts · frontend/"]

        API["🔀 API Gateway
        FastAPI · asyncpg · :8002
        JWT auth · AES-256-GCM encryption
        Rate limiting · Security headers
        11 router modules"]

        subgraph Workers ["⚙️ Celery Workers"]
            Gov["🛡️ Governance
            queue: governance
            2-node LangGraph: intake + guardrail"]

            SQL["🗃️ worker-sql
            queues: pillar.sql/.sqlite/.postgresql
            12-node Cyclic StateGraph
            HITL · Reflection · Hybrid Fusion"]

            CSV["📊 worker-csv
            queue: pillar.csv
            11-node Cyclic StateGraph
            Data Cleaning · Guardrail · Reflection"]

            JSON["📄 worker-json
            queue: pillar.json
            10-node Cyclic StateGraph
            MongoDB · Qdrant RAG"]

            PDF["📑 worker-pdf
            queue: pillar.pdf
            10-node Orchestrator StateGraph
            Gemini 2.0 Flash Vision · Triple-Engine"]

            Code["💻 worker-code
            queue: pillar.code
            8-node Cyclic StateGraph
            Neo4j AST · Cypher generation"]

            Audio["🎙️ worker-audio
            queue: pillar.audio
            Direct task — Gemini 1.5 Flash
            Transcript · Speaker · Neo4j sync"]

            Image["🖼️ worker-image
            queue: pillar.image
            Direct task — Gemini Vision
            Object/Scene · Neo4j sync"]

            Video["🎬 worker-video
            queue: pillar.video
            Direct task — Gemini Vision
            Scene/Event · Neo4j sync"]

            Nexus["🕸️ worker-nexus
            queue: pillar.nexus
            6-node Federated Orchestrator
            Neo4j forge → 5-pillar synthesis"]

            Exp["📦 exporter
            queue: export
            PDF / XLSX / JSON report generation"]
        end

        subgraph Storage ["💾 Storage Layer"]
            PG["PostgreSQL :5433
            Tenants · Users · Jobs
            Results · Policies · Groups
            Insight Memory · Metrics"]

            Redis["Redis :6379
            Celery broker + result backend
            JWT JTI blacklist
            LangGraph HITL checkpoints
            Semantic cache"]

            QdrantLocal["Qdrant :6333
            JSON RAG vectors
            PDF chunk embeddings"]

            Neo4jDB["Neo4j :7687
            Code AST graph
            Audio/Image/Video entities
            Cross-pillar relationships"]

            MongoDB["MongoDB :27017
            JSON document store
            Aggregation pipeline target"]

            Vol["Shared Volume ./tenants/
            Uploaded files (all types)
            Exported PDF/XLSX reports"]
        end

        subgraph Observability ["📈 Observability"]
            Prom["Prometheus :9090
            Metrics scraping"]
            Graf["Grafana :3000
            Pre-provisioned dashboards"]
        end
    end

    OpenRouter["☁️ OpenRouter API
    Gemini 2.0 Flash (primary)"]
    Groq["☁️ Groq API (fallback 1)"]
    GeminiAPI["☁️ Gemini Direct (fallback 2)"]

    User    -->|"HTTPS"| UI
    User    -->|"HTTPS"| ReactUI
    UI      ==>|"WSS (Real-time Streaming)"| API
    ReactUI ==>|"WSS (Real-time Streaming)"| API
    UI      -->|"fetch REST"| API
    ReactUI -->|"fetch REST"| API
    Workers ==>|"gRPC (Internal Auth)"| CorporateService["Corporate Service"]
    style CorporateService fill:#4a148c,color:#fff
    API     -->|"Celery task dispatch"| Redis
    Redis   -->|"task pickup"| Gov
    Gov     -->|"Celery task dispatch"| Redis
    Redis   -->|"task pickup"| SQL
    Redis   -->|"task pickup"| CSV
    Redis   -->|"task pickup"| JSON
    Redis   -->|"task pickup"| PDF
    Redis   -->|"task pickup"| Code
    Redis   -->|"task pickup"| Audio
    Redis   -->|"task pickup"| Image
    Redis   -->|"task pickup"| Video
    Redis   -->|"task pickup"| Nexus
    Redis   -->|"task pickup"| Exp
    API     -->|"asyncpg SQL"| PG
    SQL     -->|"asyncpg SQL"| PG
    CSV     -->|"asyncpg SQL"| PG
    JSON    -->|"asyncpg SQL"| PG
    PDF     -->|"asyncpg SQL"| PG
    Code    -->|"asyncpg SQL"| PG
    SQL     -->|"LangGraph HITL checkpoint"| Redis
    SQL     -->|"vector search (hybrid fusion)"| QdrantLocal
    JSON    -->|"vector search (RAG)"| QdrantLocal
    PDF     -->|"chunk indexing + search"| QdrantLocal
    Code    -->|"Cypher query"| Neo4jDB
    Audio   -->|"entity upsert"| Neo4jDB
    Image   -->|"entity upsert"| Neo4jDB
    Video   -->|"entity upsert"| Neo4jDB
    Nexus   -->|"cross-link forge + read"| Neo4jDB
    JSON    -->|"document query"| MongoDB
    API     -->|"file I/O"| Vol
    PDF     -->|"file I/O"| Vol
    Audio   -->|"file read"| Vol
    Image   -->|"file read"| Vol
    Video   -->|"file read"| Vol
    Exp     -->|"report write"| Vol
    SQL     -->|"LLM calls"| OpenRouter
    CSV     -->|"LLM calls"| OpenRouter
    JSON    -->|"LLM calls"| OpenRouter
    PDF     -->|"Vision + LLM calls"| GeminiAPI
    Code    -->|"LLM calls"| OpenRouter
    Audio   -->|"Gemini multimodal"| OpenRouter
    Image   -->|"Gemini multimodal"| GeminiAPI
    Video   -->|"Gemini multimodal"| GeminiAPI
    Nexus   -->|"LLM calls"| OpenRouter
    Gov     -->|"LLM calls"| OpenRouter
    OpenRouter -->|"fallback"| Groq
    OpenRouter -->|"fallback"| GeminiAPI
    API     -->|"expose /metrics"| Prom
    Prom    -->|"data source"| Graf

    style API fill:#1F6B4E,color:#fff
    style Redis fill:#DC382D,color:#fff
    style PG fill:#336791,color:#fff
    style QdrantLocal fill:#4F46E5,color:#fff
    style Neo4jDB fill:#018BFF,color:#fff
    style MongoDB fill:#47A248,color:#fff
    style Gov fill:#E74C3C,color:#fff
    style SQL fill:#27AE60,color:#fff
    style PDF fill:#4285F4,color:#fff
    style Nexus fill:#9B59B6,color:#fff
    style Code fill:#FF6B35,color:#fff
```

---

## Level 3 — Component Diagram: API Gateway

*What are the major components inside the API Gateway container?*

```mermaid
graph LR
    Client["Browser / API Client"]

    subgraph API ["services/api — FastAPI :8002 — Clean Architecture"]
        MW["Middleware Stack
        CORS · Rate Limit (slowapi)
        Security Headers · structlog"]

        subgraph Routers ["Routers (11 router modules)"]
            AuthR["auth.py
            register · login
            refresh · logout"]

            DSR["data_sources.py
            upload · connect
            list · delete · auto-analysis"]

            AnalR["analysis.py
            query · status · approve
            reject · result · history"]

            KnowR["knowledge.py
            upload PDF · list · delete"]

            PolR["policies.py
            create · list · update · delete"]

            MetR["metrics.py
            summary · jobs · latency"]

            RepR["reports.py
            export · status · download"]

            GrpR["groups.py
            create · list · assign users"]

            VoiR["voice.py
            voice-to-text query submission"]

            WSAnalR["ws_analysis.py
            WebSocket stream · job thinking steps"]
        end

        subgraph Infra ["Infrastructure (Clean Arch: outermost ring)"]
            Sec["security.py
            JWT issue/verify
            bcrypt · JTI blacklist"]

            Guard["sql_guard.py
            Layer 1: SELECT-only allowlist
            Layer 2: keyword regex blocklist"]

            Enc["encryption.py
            AES-256-GCM
            encrypt/decrypt SQL creds"]

            LLMFac["llm.py
            OpenRouter → Groq → Gemini
            Multi-provider fallback chain"]

            QdrantA["qdrant.py
            multi-vector upsert
            similarity search"]

            StorA["storage.py
            tenant-scoped paths
            file read/write"]
        end

        subgraph UC ["Use Cases (Application layer)"]
            Pipeline["run_pipeline.py
            Celery dispatch
            governance → pillar"]

            AutoA["auto_analysis.py
            5 pre-generated insights
            on data source upload"]

            Export["export.py
            Celery dispatch
            exporter queue"]
        end

        Static["static/
        Glassmorphism SPA
        HTML + CSS + JS + ECharts"]
    end

    PG["PostgreSQL"]
    Redis["Redis"]

    Client --> MW --> Routers
    AuthR --> Sec
    AuthR --> PG
    DSR --> Enc
    DSR --> StorA
    DSR --> AutoA
    AnalR --> Guard
    AnalR --> Pipeline
    AnalR --> PG
    KnowR --> QdrantA
    RepR --> Export
    Pipeline --> Redis
    AutoA --> Redis
    Export --> Redis
    Sec --> Redis
    VoiR --> Pipeline

    style MW fill:#FF6B35,color:#fff
    style Guard fill:#E74C3C,color:#fff
    style Enc fill:#8E44AD,color:#fff
    style LLMFac fill:#4285F4,color:#fff
```

---

## Level 3 — Component Diagram: SQL Worker

*What are the 12 nodes inside the SQL analysis worker?*

```mermaid
graph TD
    Celery["Celery Task Entry
    queues: pillar.sql / pillar.sqlite / pillar.postgresql"]

    subgraph SQLWorker ["services/worker-sql — 12-node Cyclic StateGraph"]
        WF["workflow.py
        LangGraph StateGraph
        AsyncRedisSaver checkpointer
        interrupt_after=['human_approval']"]

        subgraph Agents ["Agents (12 nodes)"]
            DD["data_discovery
            Schema profiling · low-cardinality
            sampling · Mermaid ERD"]

            AG["analysis_generator
            ReAct agent · golden SQL
            retrieval · ANSI SELECT"]

            RF["reflection
            Corrective hint injection
            retry_count tracking"]

            HA["human_approval
            INTERRUPT node
            State → Redis
            Waits for POST /approve"]

            EX["execution
            Live SQL (≤1,000 rows)
            row_count capture"]

            HF["hybrid_fusion
            Qdrant vector search
            PDF context enrichment"]

            VZ["visualization
            ECharts / Plotly JSON
            intent-aware chart selection"]

            IN["insight
            3–5 sentence summary
            grounded in row values"]

            VR["verifier
            Quality gate
            insight vs data check"]

            RC["recommendation
            3 actionable next steps
            intent-aware"]

            SC["save_cache
            Semantic cache save
            Qdrant vector upsert"]

            OA["output_assembler
            Final JSON build
            PostgreSQL write · job → done"]
        end

        subgraph Tools ["Tools"]
            RunSQL["run_sql_query
            dry-run + live mode
            row_count + snapshot"]

            SchDisc["sql_schema_discovery
            table profiling
            sample value extraction"]
        end

        subgraph Utils ["Utils"]
            GS["golden_sql
            retrieve similar past
            question→SQL pairs"]

            SM["schema_mapper
            column type normalization
            FK/PK detection"]

            SS["schema_selector
            FastEmbed Vector Semantic
            Routing to relevant tables"]

            SV["sql_validator
            syntax pre-check
            before routing"]
        end
    end

    Redis["Redis — HITL state checkpoint"]
    LLM["OpenRouter / Groq / Gemini — LLM inference"]
    PG["PostgreSQL — AnalysisResult write"]

    Celery --> WF
    WF --> DD --> AG
    AG -->|"error"| RF --> EX
    AG -->|"human job"| HA -->|"resume on approve"| EX
    AG -->|"auto_analysis"| EX
    EX -->|"error/0 rows + retry<3"| RF
    EX -->|"success"| HF --> VZ --> IN --> VR --> RC --> SC --> OA
    WF <-->|"state checkpoint"| Redis
    AG --> LLM
    IN --> LLM
    VR --> LLM
    RC --> LLM
    SchDisc -.-> DD
    GS -.-> AG
    RunSQL -.-> EX
    OA --> PG

    style HA fill:#FF6B35,color:#fff
    style RF fill:#E74C3C,color:#fff
    style VR fill:#27AE60,color:#fff
    style SC fill:#8E44AD,color:#fff
    style HF fill:#4285F4,color:#fff
```

---

## Level 3 — Component Diagram: CSV Worker

*What are the 11 nodes inside the CSV analysis worker?*

```mermaid
graph TD
    Celery["Celery Task Entry
    queue: pillar.csv"]

    subgraph CSVWorker ["services/worker-csv — 11-node Cyclic StateGraph"]
        WF["workflow.py
        LangGraph StateGraph
        AsyncRedisSaver checkpointer"]

        subgraph Agents ["Agents (11 nodes)"]
            DD["data_discovery
            profile_dataframe
            null ratio · outlier density
            data_quality_score"]

            DC["data_cleaning
            clean_dataframe
            null imputation · type coercion
            outlier flagging"]

            GR["guardrail
            Policy enforcement
            before analysis"]

            AN["analysis
            compute_trend / compute_ranking
            compute_correlation
            Pandas execution"]

            RF["reflection
            Code error repair
            retry_count tracking"]

            VZ["visualization
            ECharts / Plotly spec
            intent-aware chart type"]

            IN["insight
            Executive summary
            grounded in statistics"]

            VR["verifier
            Quality gate
            insight vs computed data"]

            RC["recommendation
            3 next steps
            statistics-driven"]

            OA["output_assembler
            Final JSON · PostgreSQL write"]

            SC["save_cache
            Semantic cache save"]
        end

        subgraph Tools ["Tools"]
            CT["compute_trend
            time-series aggregation"]
            CR["compute_ranking
            top-N by column"]
            CC["compute_correlation
            Pearson / Spearman matrix"]
            PDF2["profile_dataframe
            dtype · null · outlier stats"]
            CL["clean_dataframe
            imputation · coercion"]
        end
    end

    LLM["OpenRouter / Groq / Gemini"]
    PG["PostgreSQL"]

    Celery --> WF
    WF --> DD
    DD -->|"quality < 0.9"| DC --> GR
    DD -->|"quality >= 0.9"| GR --> AN
    AN -->|"error + retry<3"| RF --> AN
    AN -->|"success"| VZ --> IN --> VR --> RC --> OA --> SC
    AN --> LLM
    IN --> LLM
    VR --> LLM
    CT -.-> AN
    CR -.-> AN
    CC -.-> AN
    PDF2 -.-> DD
    CL -.-> DC
    OA --> PG

    style DC fill:#FF6B35,color:#fff
    style RF fill:#E74C3C,color:#fff
    style VR fill:#27AE60,color:#fff
    style GR fill:#8E44AD,color:#fff
```

---

## Level 3 — Component Diagram: PDF Worker (Orchestrator)

*What are the 10 nodes inside the PDF Orchestrator worker?*

```mermaid
graph TD
    Celery["Celery Task Entry
    queue: pillar.pdf"]

    subgraph PDFWorker ["services/worker-pdf — 10-node Orchestrator StateGraph"]
        WF["workflow.py
        Master Orchestrator
        Adaptive multi-pathway routing
        Anti-hallucination loop"]

        subgraph Agents ["Agents & Flows (10 nodes)"]
            RF["refine
            query_refiner_agent
            Rewrites question for
            optimal RAG retrieval"]

            RT["router
            router_agent
            greeting vs analysis
            classification"]

            CH["chat
            chat_agent
            Direct LLM response
            no retrieval needed"]

            RTV["retrieval
            adaptive_retrieval_agent
            Qdrant vector search
            reflection_needed detection"]

            VS["vision_synthesis
            Gemini 2.0 Flash Vision
            PDF pages as JPEG base64
            Multimodal LLM synthesis"]

            TS["text_synthesis
            fast_text_agent
            Clean PDF text extraction
            + LLM synthesis"]

            OS["ocr_synthesis
            hybrid_ocr_agent
            Tesseract / PaddleOCR
            + LLM synthesis"]

            VR["verifier
            verifier_agent
            Anti-hallucination gate
            Answer vs context check"]

            AN["analyst
            analyst_agent
            Final analytical summary
            + structured output"]

            OA["output_assembler
            Final JSON build
            PostgreSQL write"]
        end
    end

    Qdrant["Qdrant :6333
    Chunk embeddings + search"]
    GeminiVision["Google Gemini 2.0 Flash
    Native Multimodal Vision API"]
    LLM["OpenRouter / Groq"]
    PG["PostgreSQL"]

    Celery --> WF
    WF --> RF --> RT
    RT -->|"greeting"| CH --> OA
    RT -->|"analysis"| RTV
    RTV -->|"reflection_needed"| RF
    RTV -->|"mode=deep_vision"| VS --> VR
    RTV -->|"mode=fast_text"| TS --> VR
    RTV -->|"mode=hybrid"| OS --> VR
    VR -->|"verified=False + retry<2"| VS
    VR -->|"verified=False + retry<2"| TS
    VR -->|"verified=False + retry<2"| OS
    VR -->|"verified=True"| AN --> OA
    RTV --> Qdrant
    VS --> GeminiVision
    TS --> LLM
    OS --> LLM
    AN --> LLM
    OA --> PG

    style RF fill:#FF6B35,color:#fff
    style VR fill:#E74C3C,color:#fff
    style VS fill:#4285F4,color:#fff
    style RT fill:#8E44AD,color:#fff
    style AN fill:#27AE60,color:#fff
```

---

## Level 3 — Component Diagram: Code Worker

*What are the 8 nodes inside the Codebase analysis worker?*

```mermaid
graph TD
    Celery["Celery Task Entry
    queue: pillar.code"]

    subgraph CodeWorker ["services/worker-code — 8-node Cyclic StateGraph"]
        WF["workflow.py
        LangGraph StateGraph
        Neo4j AST-mapped codebase
        MAX_RETRIES = 3"]

        subgraph Agents ["Agents (8 nodes)"]
            DD["discovery
            Neo4j schema description
            node labels · rel types
            live stats · sample summaries"]

            GEN["generator
            cypher_generator_agent
            LLM: question → Cypher query
            schema-grounded generation"]

            RF["reflection
            reflection_agent
            Repair invalid Cypher
            retry_count tracking"]

            EX["execution
            cypher_execution_node
            Run Cypher on Neo4j
            shared pool singleton"]

            IN["insight
            insight_agent
            LLM: results + code snippets
            → narrative explanation"]

            MEM["memory
            memory_manager_agent
            Sliding window episodic summary"]

            SC["save_cache
            save_semantic_cache
            Question + Cypher + result"]

            OA["assembler
            output_assembler
            Final JSON · PostgreSQL write"]
        end
    end

    Neo4j["Neo4j :7687
    Code AST · Class/Function/File
    Relationship graph"]
    LLM["OpenRouter / Groq / Gemini"]
    PG["PostgreSQL"]

    Celery --> WF
    WF --> DD --> GEN
    GEN -->|"error + retry < MAX"| RF --> GEN
    GEN -->|"error + retry >= MAX"| EX
    GEN -->|"no error"| EX
    EX -->|"error + retry < MAX"| RF
    EX -->|"no error"| IN --> MEM --> SC --> OA
    DD --> Neo4j
    EX --> Neo4j
    GEN --> LLM
    IN --> LLM
    OA --> PG

    style RF fill:#E74C3C,color:#fff
    style EX fill:#FF6B35,color:#fff
    style MEM fill:#8E44AD,color:#fff
    style IN fill:#27AE60,color:#fff
```

---

## Level 3 — Component Diagram: Nexus Worker (Federated Orchestrator)

*How does the Nexus strategic intelligence pipeline work?*

```mermaid
graph TD
    Celery["Celery Task Entry
    queue: pillar.nexus"]

    subgraph NexusWorker ["services/worker-nexus — 6-node Federated Orchestrator"]
        WF["workflow.py
        LangGraph StateGraph
        Reads shared Neo4j Knowledge Graph"]

        subgraph Agents ["Agents (6 nodes)"]
            RT["router
            nexus_router
            Routes: explore / direct_query / finalize"]

            EX["explorer
            graph_explorer
            Discovers available pillars
            and Neo4j context"]

            OR["orchestrator
            pillar_orchestrator (inner graph)
            3 sub-nodes:
            1. discovery_node: forge cross-source links
            2. gather_context_node: collect entities + metadata
            3. synthesis_node: 5-pillar report generation"]

            SY["synthesizer
            synthesis_engine
            Final cross-pillar consolidation"]

            MEM["memory
            memory_manager_agent
            Episodic memory via Qdrant
            semantic similarity"]

            SC["save_cache
            save_semantic_cache
            Question + synthesis saved"]
        end
    end

    Neo4j["Neo4j :7687
    Cross-pillar entity graph
    REPRESENTS_DATA / ENTITY_TARGET
    CHUNK_MENTION relationships"]
    LLM["OpenRouter Gemini 2.0 Flash
    5-pillar synthesis prompt"]
    PG["PostgreSQL
    Schema/metadata per source"]
    QdrantMem["Qdrant
    Episodic memory vectors"]

    Celery --> WF
    WF --> RT
    RT -->|"explore"| EX --> OR
    RT -->|"direct_query"| OR
    RT -->|"finalize"| SY
    OR --> SY --> MEM --> SC
    OR <-->|"forge + read"| Neo4j
    OR --> PG
    SY --> LLM
    MEM --> QdrantMem

    style OR fill:#9B59B6,color:#fff
    style RT fill:#FF6B35,color:#fff
    style SY fill:#4285F4,color:#fff
    style MEM fill:#8E44AD,color:#fff
```

---

## Level 3 — Component Diagram: Governance Worker

*What are the components inside the Governance worker?*

```mermaid
graph LR
    Celery["Celery Task
    queue: governance"]

    subgraph GovWorker ["services/governance — 2-node LangGraph StateGraph"]
        WF["workflow.py
        StateGraph: intake → guardrail"]

        subgraph Agents ["Agents"]
            IA["intake_agent
            Intent classification:
            trend | comparison | ranking
            correlation | anomaly
            Entity extraction
            Ambiguity detection
            Complexity index (1–5)"]

            GA["guardrail_agent
            Load tenant active policies
            LLM semantic policy check
            PII column detection
            Violation → error status"]
        end

        Router["check_intake
        needs_clarification?
        → ask user to rephrase
        OR route to guardrail"]
    end

    PillarQ["Redis
    → pillar.sql / csv / json / pdf
    / code / audio / image / video / nexus
    Celery task dispatch"]

    LLM["OpenRouter / Groq / Gemini"]
    PG["PostgreSQL
    Tenant policies
    Job status update"]

    Celery --> WF
    WF --> IA --> Router
    Router -->|"clear"| GA --> PillarQ
    Router -->|"ambiguous"| PG
    IA --> LLM
    GA --> LLM
    GA --> PG

    style GA fill:#E74C3C,color:#fff
    style Router fill:#FF6B35,color:#fff
```

---

## Level 4 — Code Diagram: HITL Sequence

*How does Human-in-the-Loop approval work at the code level?*

```mermaid
sequenceDiagram
    participant Client
    participant API as API Gateway
    participant Redis
    participant Gov as Governance Worker
    participant SQLWorker as SQL Worker (LangGraph)
    participant Admin

    Client->>API: POST /analysis/query {question, source_id}
    API->>Redis: Dispatch governance_task (queue: governance)
    Redis->>Gov: Pick up task
    Gov->>Gov: intake_agent → intent="ranking"
    Gov->>Gov: guardrail_agent → no violations
    Gov->>Redis: Dispatch pillar_task (queue: pillar.sql)

    Redis->>SQLWorker: Pick up task
    SQLWorker->>SQLWorker: data_discovery → analysis_generator
    Note over SQLWorker: Generates optimized ANSI SELECT query
    SQLWorker->>Redis: Serialize full graph state (AsyncRedisSaver)
    Note over Redis: Key: checkpoint:{thread_id}
    SQLWorker->>SQLWorker: interrupt_after=["human_approval"] fires
    SQLWorker-->>API: Update job: status=awaiting_approval, generated_sql=...
    SQLWorker->>SQLWorker: Task exits cleanly (Celery worker freed)

    Client->>API: GET /analysis/{job_id}
    API-->>Client: { status: "awaiting_approval", generated_sql: "SELECT..." }

    Admin->>API: POST /analysis/{job_id}/approve
    API->>Redis: aupdate_state({approval_granted: True})
    API->>Redis: Dispatch pillar_task (resume, queue: pillar.sql)
    Redis->>SQLWorker: Pick up task

    SQLWorker->>Redis: aget_state() — load checkpoint
    Note over SQLWorker: Graph resumes from human_approval node
    SQLWorker->>SQLWorker: execution → hybrid_fusion → visualization
    SQLWorker->>SQLWorker: insight → verifier → recommendation → save_cache
    SQLWorker-->>API: Insert AnalysisResult, status=done

    Client->>API: GET /analysis/{job_id}/result
    API-->>Client: { charts, insight_report, exec_summary, recommendations, follow_up_suggestions }
```

---

## Level 4 — Code Diagram: Zero-Row Reflection

*How does the SQL agent heal itself when a query returns no results?*

```mermaid
sequenceDiagram
    participant Gen as analysis_generator
    participant Exec as execution
    participant Router as route_after_execution
    participant Ref as reflection
    participant State as LangGraph State (Redis)

    Gen->>State: Write generated_sql = "SELECT ... WHERE quarter = 'q4'"
    Gen->>Exec: Route → execution
    Exec->>Exec: Run SQL against live DB
    Exec->>State: Write row_count = 0, reflection_context = null

    Exec->>Router: route_after_execution()
    Router->>State: Read row_count = 0, retry_count = 0
    Note over Router: row_count=0 + retry<3 → reflection path
    Router->>State: Extract SQL literals: ["q4"]
    Router->>State: Compare against low_cardinality_values: quarter=["Q1","Q2","Q3","Q4"]
    Router->>State: Write reflection_context = "Case mismatch: 'q4' → 'Q4'"
    Router->>Ref: Route → reflection

    Ref->>State: Read reflection_context
    Ref->>State: Write hint = "Retry with exact case: 'Q4'"
    Ref->>State: Increment retry_count (now 1 of 3)
    Ref->>Exec: Route → execution (bypass analysis_generator)

    Exec->>Exec: Run corrected SQL "WHERE quarter = 'Q4'"
    Exec->>State: Write row_count = 5 ✓
    Exec->>Router: route_after_execution()
    Router->>Router: row_count > 0 + no error → success path
    Router->>Router: Route → hybrid_fusion
```

---

## Level 4 — Code Diagram: PDF Anti-Hallucination Loop

*How does the PDF worker verify its own answers?*

```mermaid
sequenceDiagram
    participant Ret as retrieval (Qdrant)
    participant VS as vision_synthesis (Gemini 2.0 Flash)
    participant VR as verifier
    participant AN as analyst
    participant State as LangGraph State

    Ret->>State: Write retrieved_chunks, pages=[3,7,12]
    Ret->>State: analysis_mode = "deep_vision"
    Ret->>VS: Route → vision_synthesis

    VS->>VS: Render PDF pages 3,7,12 as JPEG base64
    VS->>VS: POST to Gemini 2.0 Flash Vision API
    Note over VS: Multimodal: image array + text prompt
    VS->>State: Write insight_report (draft answer)

    VS->>VR: Route → verifier
    VR->>State: Read insight_report + retrieved_chunks
    VR->>VR: LLM check: Is every claim in insight_report grounded in chunks?
    VR->>State: Write verified=False, retry_count=1

    Note over VR: Anti-hallucination loop triggers
    VR->>VS: Route back → vision_synthesis (retry)

    VS->>VS: Re-synthesize with stricter grounding prompt
    VS->>State: Write insight_report (revised, grounded)
    VS->>VR: Route → verifier

    VR->>State: Read revised insight_report
    VR->>VR: All claims verified against source pages ✓
    VR->>State: Write verified=True
    VR->>AN: Route → analyst

    AN->>AN: Structured analytical summary
    AN->>State: Write final output_assembler input
```

---

## Level 4 — Code Diagram: Nexus Cross-Pillar Entity Forge

*How does the Nexus worker create cross-domain relationships in Neo4j?*

```mermaid
sequenceDiagram
    participant Client
    participant API as API Gateway
    participant Nexus as Nexus Worker
    participant Neo4j
    participant LLM as Gemini 2.0 Flash (OpenRouter)
    participant PG as PostgreSQL

    Client->>API: POST /analysis/query {source_ids=[sql_id, code_id, pdf_id], question}
    API->>Nexus: Celery task → queue: pillar.nexus

    Nexus->>Nexus: nexus_router → route="explore"
    Nexus->>Nexus: graph_explorer → discover pillars

    Note over Nexus: pillar_orchestrator enters inner graph

    Nexus->>Neo4j: forge_cross_source_links(source_ids)
    Note over Neo4j: Match(Class) ↔ Match(Table) by name → CREATE :REPRESENTS_DATA
    Note over Neo4j: Match(Entity) ↔ Match(Column) → CREATE :ENTITY_TARGET
    Note over Neo4j: Match(Chunk) ↔ Match(Function) → CREATE :CHUNK_MENTION
    Neo4j-->>Nexus: forge_counts {class_table: 12, entity_target: 8, chunk_mention: 5}

    Nexus->>Neo4j: fetch_multi_source_context(source_ids)
    Neo4j-->>Nexus: {entities: [...], cross_pillar_links: [...]}

    Nexus->>PG: SELECT type, file_path, schema_json FROM data_sources WHERE id IN (...)
    PG-->>Nexus: metadata per source

    Note over Nexus: Bucket entities by pillar: sql/csv/json/pdf/codebase
    Note over Nexus: Build 5-section cross-pillar context block

    Nexus->>LLM: 5-pillar synthesis prompt (entities + cross-links + episodic memory)
    LLM-->>Nexus: Executive Strategic Intelligence Report (5 sections)

    Nexus->>PG: INSERT AnalysisResult, UPDATE job status → done
    Nexus-->>Client: { synthesis, thinking_steps, cross_pillar_links }
```

---

## Architecture Decision Records (ADR)

| Decision | Choice | Rejected Alternatives | Rationale |
|---|---|---|---|
| Inter-service communication | Celery + Redis queues | Direct HTTP, gRPC | Decoupling — API works even when workers are restarting |
| Service internal structure | Clean Architecture (Hexagonal) | MVC, flat scripts | Dependency Inversion: infrastructure changes don't touch domain logic |
| HITL state persistence | Redis (`AsyncRedisSaver`) | PostgreSQL, in-memory | Survives worker restart; Redis is already in the stack |
| LLM primary provider | OpenRouter (Gemini 2.0 Flash) | Groq Llama, OpenAI GPT-4 | Multimodal capability for PDF + cost efficiency + OpenRouter fallback routing |
| LLM fallback strategy | `with_fallbacks([Groq, Gemini Direct])` | Single provider, manual retry | Zero-downtime LLM provider outages; transparent to all agents |
| PDF synthesis | Gemini 2.0 Flash Vision (multimodal) | ColPali multi-vector, text chunking | Native multimodal: no separate embedding model; preserves visual layout, tables, charts |
| Vector search (JSON/PDF) | Qdrant (768d) | Pinecone, Weaviate, pgvector | Self-hosted; free; excellent async Python SDK; supports multi-vector |
| Knowledge graph | Neo4j | pgvector, plain Postgres | Native graph traversal for cross-pillar relationships; Cypher is purpose-built for path queries |
| Credential encryption | AES-256-GCM in DB | AWS Secrets Manager, HashiCorp Vault | Zero external dependencies; clear migration path to secrets manager |
| Tenant isolation | Shared DB + `tenant_id` | One DB per tenant | Simpler ops at current scale; equivalent isolation guarantee via SQLAlchemy scoping |
| Frontend | Vanilla JS SPA + React/TS | Angular, Vue | Vanilla for zero-build-step demo; React for production component reuse |
| Observability | Prometheus + Grafana | Datadog, New Relic | Self-hosted; zero cost; provisioned automatically via Docker Compose |
| LangGraph graph type | `StateGraph` (Cyclic) | `MessageGraph`, linear chains | Cycles required for reflection loops, HITL, and anti-hallucination retries |
| Audio/Image/Video processing | Direct Celery task (Gemini multimodal) | Custom LangGraph pipeline | Indexing is one-shot, not iterative — no cycles needed; simpler, faster |
| Cross-pillar intelligence | Neo4j knowledge graph + Nexus worker | Per-query cross-service HTTP calls | Pre-forged relationships enable millisecond graph traversal; avoids live cross-service coupling |
