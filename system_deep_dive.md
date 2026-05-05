# OpenQ — Full System Deep Dive
## Service-by-Service | File-by-File | Complete Flow

---

## 🗺️ الصورة الكبيرة أول

```
User → API → Redis (Queue) → Workers (Indexing/Analysis) → Neo4j + Qdrant + Postgres
                                                                      ↓
                                                            worker-nexus (Orchestrator)
                                                                      ↓
                                                              Final Report → User
```

**المنصة عبارة عن 11 Microservice:**
| Service | Role |
|---------|------|
| `api` | FastAPI — Gateway + WebSocket + Auth |
| `worker-pdf` | PDF/DOCX/XLSX/Images Indexing + Analysis |
| `worker-sql` | SQL DB Schema Extraction + NL-to-SQL |
| `worker-code` | Codebase AST Parsing + Graph Reasoning |
| `worker-audio` | Audio Diarization + Entity Extraction |
| `worker-json` | JSON/CSV Structured Data |
| `worker-nexus` | 🧠 Universal Orchestrator (GraphRAG) |
| `worker-vision` | Computer Vision / Employee Tracking |
| `governance` | RBAC / Policy Enforcement |
| `corporate` | Corporate Dashboard / Strategic Reports |
| `exporter` | Report Export (PDF, DOCX) |

---

## 🔄 الفلو الكامل: من السؤال للإجابة

### Phase 1: User يرفع ملف/قاعدة بيانات/Repo

```
User → POST /api/data-sources → api/app/routers/data_sources.py
     → يُسجَّل في Postgres (data_sources table)
     → Celery task يتبعت لـ Redis queue المناسبة
```

### Phase 2: الـ Specialist Worker يعالج

كل Worker بياخد الـ Job ويشتغل مستقل تماماً.

### Phase 3: Worker يبعت الـ Payload للـ Nexus

بعد ما ينهي الـ Indexing، بيبعت للـ Nexus عشان يضيفه للـ Knowledge Graph.

### Phase 4: User يسأل سؤال

```
User → POST /api/analysis → api/app/routers/analysis.py
     → analysis_jobs record في Postgres
     → task "nexus.analyze" يتبعت لـ queue "pillar.nexus"
```

### Phase 5: worker-nexus يجاوب

LangGraph pipeline كامل → Final Report → يتحفظ في Postgres → يتبعت للـ User.

---

## 📁 Service-by-Service Deep Dive

---

### 🔵 1. `api` — The Gateway

**الدور:** الواجهة الوحيدة للخارج. بيستقبل كل الـ HTTP Requests والـ WebSocket Connections.

#### `app/main.py`
- `lifespan()`: عند بدء التشغيل، بيعمل Self-Healing Database Schema بـ `pg_try_advisory_lock` (Advisory Lock) عشان يمنع الـ Race Conditions لو أكتر من Instance اشتغل في نفس الوقت.
- بيـ import كل الـ Routers: `auth, users, data_sources, analysis, reports, knowledge, codebase, voice`
- Prometheus Instrumentator مربوط على كل الـ Endpoints.

#### `app/routers/analysis.py`
- `POST /analysis`: بيعمل `analysis_jobs` record في Postgres بـ status `pending`, وبعدين بيبعت Celery task لـ Queue المناسبة.
- **الذكاء هنا:** بيشوف نوع الـ Source (pdf, sql, code) ويبعت للـ Queue الصح.

#### `app/routers/data_sources.py`
- `POST /data-sources`: يستقبل الملف، يعمل Chunking أولي، يبعت الـ Indexing task.

---

### 🟢 2. `worker-pdf` — Document Intelligence Pillar

**الدور:** بيفهم كل أنواع الـ Documents (21 نوع) ويحولهم لـ Knowledge.

#### `app/worker.py`
- Celery task: `pillar_task(job_id)`
- بيستخدم `AsyncRedisSaver` كـ LangGraph Checkpointer للـ Fault Tolerance.
- يشغّل `build_pdf_graph()` — LangGraph workflow مخصص للـ PDF.

#### `app/modules/pdf/workflow.py` (LangGraph)
Flow الـ PDF:
```
START → strategy_selector → loader → chunker → embedder → entity_extractor → evaluator → nexus_bridge → END
```

- **strategy_selector**: بيحدد الـ Strategy (Fast/Auto/Hi-res/OCR) بناءً على نوع الملف.
- **loader**: `unstructured` library بتدعم 21 نوع ملف.
- **chunker**: Parent-Child Chunking مع `atomic=True` عشان الجداول والـ Code Blocks ما تتكسرش.
- **embedder**: `multilingual-e5-large` (1024d) via FastEmbed — Local, Zero API Cost.
- **entity_extractor**: LLM (Gemini 2.0 Flash Lite) بيستخرج Named Entities من كل Chunk.
- **evaluator**: `rag_evaluator.py`:
  - `cross-encoder/ms-marco-MiniLM-L-6-v2` → Relevance Score
  - `cross-encoder/nli-deberta-v3-small` → Attribution/Hallucination Score
  - `utilization` Score → كام من الـ Chunk اتستخدم فعلاً
- **nexus_bridge**: يبعت الـ payload للـ Nexus Queue عشان يعمل Graph Indexing.

#### `app/modules/pdf/utils/rag_evaluator.py`
```python
# 3 Signals بيتحسبوا في نفس الـ pass:
relevance   = cross_encoder_ms_marco(query, chunk)   # هل الـ Chunk مرتبط؟
attribution = nli_deberta(chunk, response)            # هل الإجابة grounded؟
utilization = sentence_nli(chunk, response)           # كام من الـ Chunk اتستخدم؟
```

---

### 🟡 3. `worker-sql` — Database Schema Intelligence

**الدور:** يفهم Schema قاعدة البيانات ويعمل Natural Language to SQL.

#### `app/worker.py`
- Celery task: `pillar_task(job_id)`
- يشغّل `build_sql_workflow()` — LangGraph للـ SQL.

#### SQL Workflow Flow:
```
START → schema_extractor → graph_builder → nl_to_sql_agent → sql_executor → insight_agent → evaluator → nexus_bridge → END
```

- **schema_extractor**: بيتوصل لقاعدة البيانات ويستخرج Tables/Columns/Foreign Keys.
- **graph_builder**: يبني Neo4j nodes في Postgres (كـ JSON) تمهيداً للـ Nexus.
- **nl_to_sql_agent**: DeepSeek V3 (عشان code/schema comprehension) بيحوّل السؤال لـ SQL.
- **sql_executor**: بينفذ الـ SQL على الـ DB الفعلي.
- **evaluator**: نفس الـ Cross-Encoders من الـ PDF.
- **nexus_bridge**: يبعت (Tables, Columns, Foreign Keys) للـ Nexus.

---

### 🟣 4. `worker-code` — Codebase Graph Intelligence

**الدور:** يفهم الكود كـ Structured Logic مش كـ Plain Text.

#### `app/use_cases/ingestion/service.py` — الأهم
```
1. CodeExtractor.extract_or_clone()  → يجيب الـ Repo من GitHub أو ZIP
2. ASTParser.parse_file()            → Tree-sitter (Python/JS/Java/C++/Go/Rust/...)
   ↓ يستخرج: Classes, Functions, Imports, Call Graph
3. CodeEnricher.semantic_summarize() → DeepSeek V3 يعمل Ontology لكل Function:
   {summary, semantic_archetype, inferred_domain, execution_nature, 
    architectural_layer, structural_health}
4. enricher.embed(summary)           → StarEncoder (768d) للـ Code Embeddings
5. CodeStore.save()                  → يحفظ الكود كـ .txt files (بالـ chunk_id)
   [لو حفظناه في Neo4j هيبطئ الـ Queries]
6. adapter.batch_upsert_entities()   → يكتب في Neo4j
7. semantic_weaver.run()             → Neo4j GDS:
   - k-NN → SEMANTICALLY_SIMILAR edges
   - Louvain Community Detection → architectural_module_id
   - PageRank → architectural_importance
```

#### `app/infrastructure/ast_parser.py`
- بيستخدم `tree-sitter` مع 10 لغات برمجة.
- الـ "Chunk" هنا مش text chunk عشوائي — ده **دالة كاملة** أو **class كامل** بحدودها الدقيقة.

#### `app/modules/code/agents/retrieval/` — LangGraph للـ Q&A
```
START → discovery → generator → execution → insight → evaluator → memory → save_cache → assembler → END
             ↑__________________________|  (Reflection + Retry Loop, max 3)
```
- **discovery**: يجيب Schema حقيقي من Neo4j.
- **generator**: DeepSeek V3 يولد Cypher Query.
- **execution**: ينفذ الـ Cypher على Neo4j.
- **insight**: يجيب الكود الفعلي من `CodeStore` ويولد الإجابة.
- **memory**: Sliding Window Memory (آخر 4 Messages).
- **save_cache**: `nomic-embed-text-v1.5` (768d) للـ Semantic Caching في Qdrant.

---

### 🟠 5. `worker-audio` — Conversational Intelligence

**الدور:** بيفهم المحادثات الصوتية (Meetings) ويحولها لـ Knowledge Graph.

#### Audio Pipeline Flow:
```
START → normalizer → transcriber → diarization → entity_extractor → quality_gate → storage → nexus_bridge → END
```

- **transcriber**: Gemini 2.5 Flash بـ Base64 Audio (Multimodal) — مش Whisper تقليدي.
  - بيكـ capture الـ Prosody والـ Tone.
- **diarization**: بيـ map SPEAKER_XX لأسماء حقيقية.
- **entity_extractor**: Llama-3.1-8B بيستخرج الـ Entities.
- **quality_gate**: NLI DeBERTa بيحسب Attribution Score.
  - لو الـ Insight مش Entailed → Reject + Error State (Zero Hallucination Policy).
- **storage**: Parallel:
  - Qdrant (Semantic Search).
  - Neo4j: `(Speaker)-[:SPOKE]->(Turn)-[:MENTIONS]->(Entity)`.
  - UUID5 Hashes للـ ID generation عشان 1:1 Parity بين الـ DBs.
- **Semantic Cache**: Cosine Similarity > 0.92 → Bypass Pipeline كامل.

---

### 🔴 6. `worker-nexus` — The Omniscient Orchestrator

**الدور:** العقل المدبر. بيستقبل من كل الـ Workers ويبني الـ Universal Knowledge Graph وبيجاوب الأسئلة المعقدة.

#### `app/worker.py` — Entry Point
```python
@celery_app.task(name="nexus.analyze", queue="pillar.nexus")
def nexus_task(job_id: str):
    # 1. يجيب الـ Job من Postgres (source_ids + question)
    # 2. يشغّل run_nexus_pipeline(payload)
    # 3. يحفظ النتيجة في analysis_jobs + analysis_results
```

#### `app/modules/indexing/` — Federated Sinks

##### `pdf_indexer.py`
```python
# يستخدم: LexicalGraphBuilder + Neo4jWriter (neo4j-graphrag)
# Input: {source_id, chunks: [{id, text, embedding, metadata, entities}]}
# Output في Neo4j:
Document node
  ↑ FROM_DOCUMENT
Chunk node → NEXT_CHUNK → Chunk node  (Sequential Order)
  ↓ MENTIONS
Entity node  (pre-extracted من worker-pdf)

# الـ chunk_metadata (page_number, section) بتدخل كـ properties ديناميكياً
# Neo4jWriter.run() → Upsert بـ batch_size=500, clean_db=False
```

##### `code_indexer.py`
```python
# يستخدم: SchemaBuilder + Neo4jWriter (neo4j-graphrag)
# Input: {source_id, files, classes, functions, function_calls, imports}
# Output في Neo4j:
(File) nodes
(Class)-[:DEFINED_IN]->(File)
(Class)-[:HAS_FUNCTION]->(Function)
(Function)-[:CALLS]->(Function)      # Call Graph
(File)-[:IMPORTS]->(File)            # Dependency Graph

# صفر LLM — الـ Schema حُدّد بـ SchemaBuilder بشكل Deterministic
```

##### `sql_indexer.py`
```python
# يستخدم: SchemaBuilder + Neo4jWriter (neo4j-graphrag)
# Input: {source_id, tables, columns, foreign_keys}
# Output في Neo4j:
(Table)-[:HAS_COLUMN]->(Column)
(Column)-[:FOREIGN_KEY_TO]->(Column)   # ERD كامل في Neo4j!

# unique key = "table_name.column_name" لتفادي الـ Duplicates
```

##### `audio_indexer.py`
```python
# يستخدم: LexicalGraphBuilder + Neo4jWriter (neo4j-graphrag)
# Input: {source_id, speakers, turns, entities}
# Output في Neo4j:
(Speaker)-[:SPOKE]->(Turn)
(Turn)-[:MENTIONS]->(Entity)
(Turn)-[:NEXT_TURN]->(Turn)
```

---

#### `app/modules/retrieval/` — The LangGraph Intelligence Pipeline

##### `workflow.py` — Graph Topology Compiler فقط
```python
workflow.add_node("query_fusion",    query_fusion_node)
workflow.add_node("gather_context",  gather_context_node)
workflow.add_node("rerank_context",  rerank_context_node)
workflow.add_node("synthesis_layer", synthesis_node)
# Linear Flow — no conditional edges (Deterministic Pipeline)
```

##### `nodes/query_fusion.py`
```python
# LLM: Gemini 2.0 Flash (via OpenRouter)
# Input: {question}
# Process: LLM بيكسر السؤال لـ 3 sub-queries:
#   1. Structural (Code/Architecture)
#   2. Schema (SQL/Tables)
#   3. Business Logic (Docs/Policy)
# Output: {fusion_queries: [q1, q2, q3]}
# Fallback: لو فشل، يستخدم الـ Original Question
```

##### `nodes/gather_context.py`
```python
# asyncio.gather() — Parallel I/O
# 1. adapter.fetch_multi_source_context(source_ids) → Neo4j
# 2. Postgres: SELECT type, file_path, schema_json FROM data_sources
# Output: {graph_context, meta_context}
```

##### `nodes/rerank_context.py` — ⭐ الأهم
```python
# embedder: FastEmbedGraphRagWrapper (multilingual-e5-large, 1024d, local)
# llm: OpenAILLM → OpenRouter → Gemini 2.0 Flash

# Tool 1: QdrantNeo4jRetriever
#   - Vector Search في Qdrant
#   - يجيب الـ Node الكامل من Neo4j بالـ ID

# Tool 2: Text2CypherRetriever
#   - Neo4j Schema (الـ Graph اللي بنيناه):
#     (Chunk)-[:FROM_DOCUMENT]->(Document)
#     (Function)-[:CALLS]->(Function)
#     (Column)-[:FOREIGN_KEY_TO]->(Column)
#     (Speaker)-[:SPOKE]->(Turn)
#     (Chunk)-[:INFERRED_LINK_GRL]->(Class)  ← من الـ GDS
#   - LLM يولد Cypher Query ديناميكي

# ToolsRetriever: LLM يختار Tool أو الاتنين
master_retriever = ToolsRetriever(driver, llm, tools=[vector_tool, cypher_tool])

# Parallel Fusion Search:
all_results = await asyncio.gather(
    *[asyncio.to_thread(master_retriever.search, q) for q in fusion_queries]
)
# On-the-fly Deduplication بالـ Set
```

##### `nodes/synthesis.py`
```python
# llm: OpenAILLM → OpenRouter → Gemini 2.0 Flash
# memory: Neo4jMessageHistory(session_id, driver)  ← Persistent عبر الجلسات!

# StaticContextRetriever: يحقن الـ reranked_entities كـ Context جاهز
# GraphRAG.search() → RagTemplate → Final Answer

# يحفظ الـ Conversation History في Neo4j عشان الـ Auditability
```

---

#### `app/modules/graph_ops/` — Background Intelligence

##### `entity_resolver.py`
```python
# يُشغَّل كـ Scheduled Celery Task
# FuzzyMatchResolver (neo4j-graphrag):
resolver = FuzzyMatchResolver(
    driver=driver,
    node_label="Entity",              # بس Entity nodes — مش Classes أو Functions
    resolve_properties=["name", "title"],
    similarity_threshold=0.85         # RapidFuzz string distance
)
# بيدمج "AWS" مع "Amazon Web Services"
# كل الـ Relationships بتتنقل للـ Merged Node تلقائياً
```

##### `graph_learning.py`
```python
# GDSMaintenanceSession (Context Manager):
# - بيـ drop الـ Projection لو موجودة (Memory Leak Prevention)
# - بيبني Projection جديدة عند الدخول
# - بيـ drop تلقائياً عند الخروج (حتى لو فيه Exception)

# Projection: كل الـ Node Labels + كل الـ Relationships
["Document", "Chunk", "Entity", "Class", "Function", "Table", "Column", "Speaker", "Turn"]

# Step 1: FastRP (Fast Random Projection)
gds.fastRP.mutate(G,
    mutateProperty="structural_embedding",
    embeddingDimension=256,
    iterationWeights=[0.8, 1.0, 1.0]   # يركز على Local + Mid-range neighbors
)
# يكتب الـ embeddings في Neo4j nodes

# Step 2: Link Prediction Pipeline
pipe.addLinkFeature("hadamard", nodeProperties=["structural_embedding"])
# Hadamard Product: يضرب الـ embeddings عشان يعمل link vector
pipe.addRandomForest(numberOfDecisionTrees=10)
model = pipe.train(G, targetRelationshipType="MENTIONS")

# Step 3: Predict + Write
gds.beta.pipeline.linkPrediction.predict.mutate(G,
    modelName=model_name,
    mutateRelationshipType="INFERRED_LINK_GRL",
    threshold=0.85   # High Confidence فقط
)
gds.graph.writeRelationship(G, "INFERRED_LINK_GRL")
# النتيجة: الـ Graph بيكتشف وحده إن Chunk من PDF مرتبط بـ Class في Code
```

---

#### `app/infrastructure/`

##### `llm.py` — Centralized LLM Factory
```python
# STRICT OPENROUTER MODE — مفيش غيره
def get_llm(temperature=0, model=None) -> BaseChatModel:
    return ChatOpenAI(
        model=model or settings.LLM_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        max_retries=3,
        default_headers={
            "HTTP-Referer": settings.OPENROUTER_SITE_URL,
            "X-Title": settings.OPENROUTER_APP_TITLE,
        }
    )
# Legacy Groq strings يتحولوا أوتوماتيكياً لـ LLM_MODEL_FAST
```

##### `neo4j_adapter.py` — Graph DB Connection
- Connection Pooling + Transaction Management.
- `bootstrap_neo4j()`: عند بدء التشغيل بيعمل Constraints + Vector Indexes (fail-fast).
- `fetch_multi_source_context()`: بيجيب Context من Neo4j للـ gather_context node.
- `execute_nexus_bridge()`: بيربط الـ code entities بالـ nexus graph.

##### `config.py` — Pydantic Settings
```python
# LLM Routing Strategy (اللي بيخلينا نستخدم الموديل الصح في المكان الصح):
LLM_MODEL_CODE  = "deepseek/deepseek-chat-v3-0324"        # Complex Reasoning
LLM_MODEL_SQL   = "google/gemini-2.0-flash-001"           # Schema Comprehension
LLM_MODEL_PDF   = "google/gemini-2.0-flash-lite-001"      # Mass Processing
LLM_MODEL_NEXUS = "google/gemini-2.0-flash-001"           # Strategic Synthesis
LLM_MODEL_FAST  = "meta-llama/llama-3.2-3b-instruct"      # Routing/Verification
LLM_MODEL_VISION= "meta-llama/llama-3.2-11b-vision-instruct"  # Multimodal

# Embedding Models:
EMBED_MODEL_GENERAL = "intfloat/multilingual-e5-large"    # 1024d — Main RAG
EMBED_MODEL_CACHE   = "nomic-ai/nomic-embed-text-v1.5"   # 768d  — Local Cache
```

---

## 🎯 Key Architectural Decisions (للإنترفيو والبوست)

### 1. ليه Neo4j + Qdrant معاً؟
- **Qdrant**: سريع جداً في الـ Vector Search (ANN algorithms).
- **Neo4j**: بيفهم العلاقات المعقدة (traversal).
- **الاتنين معاً**: `QdrantNeo4jRetriever` بيعمل Vector Search في Qdrant وبيجيب الـ Full Node من Neo4j بالـ ID — أفضل من الاتنين لوحده.

### 2. ليه Federated Sinks وليس Pipeline واحدة؟
- كل Data Type محتاج Logic مختلف تماماً (AST vs. Lexical vs. Schema).
- الـ Nexus بيكون Pure Aggregator — مش بيعمل Processing.
- لو Sink واحدة فشلت، الباقيين بيكملوا.

### 3. ليه ToolsRetriever وليس Hybrid Search بس؟
- Hybrid Search دايماً بتعمل Vector + Fulltext في نفس الوقت — Expensive.
- ToolsRetriever: LLM بيقرر **هيعمل إيه بالظبط** — Efficient.
- بعض الأسئلة محتاجة Cypher بس (مثلاً: "كام Function بتعملوا CALLS لـ authenticate؟").

### 4. ليه Neo4jMessageHistory وليس In-Memory؟
- Persistent Memory عبر جلسات مختلفة.
- Auditability — تقدر تراجع كل المحادثات.
- لو الـ Container مات، الـ Memory محفوظة.

### 5. ليه GDSMaintenanceSession كـ Context Manager؟
- Neo4j GDS بتعمل In-Memory Projections.
- لو الـ Pipeline فشلت، الـ Projection بتفضل في الـ Memory وبتعمل Leak.
- الـ Context Manager بيضمن إن الـ Projection تتحذف دايماً.

### 6. ليه CodeStore (filesystem) وليس Neo4j property؟
- تخزين الـ Raw Code كـ Node Property في Neo4j بيبطئ كل الـ Queries.
- الـ Neo4j Property Reads بطيئة حتى لو الـ Property مش في الـ RETURN clause.
- الـ Solution: نحفظ الـ ID في Neo4j وننزل الكود on-demand من الـ Filesystem.

---

## 📊 Technology Mapping

| Technology | Where Used | Why |
|-----------|-----------|-----|
| `neo4j-graphrag` | nexus/indexers | LexicalGraphBuilder, SchemaBuilder, ToolsRetriever, FuzzyMatchResolver |
| `LangGraph` | كل Worker | Stateful, fault-tolerant agentic pipelines |
| `FastEmbed` | nexus/pdf/json | Local embeddings — Zero API cost |
| `Tree-sitter` | worker-code | Deterministic AST parsing لـ 10 لغات |
| `StarEncoder` | worker-code | Specialized code embeddings (768d) |
| `Neo4j GDS` | graph_ops | FastRP + Louvain + PageRank + Link Prediction |
| `cross-encoder/ms-marco` | كل Worker | Relevance scoring للـ Reranking |
| `NLI DeBERTa` | كل Worker | Hallucination detection |
| `Redis` | Message Broker + Cache + Checkpointer | Celery + LangGraph |
| `Prometheus + Grafana` | Observability | Metrics: attribution_rate, avg_relevance |
| `structlog` | كل Worker | Structured JSON logging |
| `pydantic-settings` | كل Worker | Config validation + Fail-Fast |
