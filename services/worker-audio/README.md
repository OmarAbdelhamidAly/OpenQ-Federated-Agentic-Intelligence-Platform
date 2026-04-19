<div align="center">

# 🎙️ Worker Audio (Enterprise Audio Intelligence Pillar)

**Advanced Multimodal Audio processing, Diarization & RAG Pipeline**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Celery Tasks](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Neo4j & Qdrant](https://img.shields.io/badge/Neo4j_%26_Qdrant-Hybrid_RAG-018BFF?logo=neo4j&logoColor=white)](https://neo4j.com)
[![LangGraph Ops](https://img.shields.io/badge/LangGraph-StateGraph-FF6B35)](https://langchain-ai.github.io/langgraph/)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-Multimodal_LLMs-black)](https://openrouter.ai/)

</div>

---

## 🎯 Overview

The `worker-audio` service is an enterprise-grade multimodal intelligence microservice within the OpenQ platform. It is designed to automatically transcribe, diarize (identify speakers), summarize, and extract semantic entities from raw audio files (`.wav`, `.mp3`, `.m4a`, etc.). 

Instead of relying on legacy, disjointed pipelines (like separate Whisper models and heavy Pyannote instances), this service leans entirely into **OpenRouter's multimodal endpoints**, specifically utilizing `gemini-2.5-flash-preview`'s native audio understanding combined with a cost-efficient **9-Node LangGraph Pipeline**.

---

## 🏗️ Architecture Deep Dive: 9-Node Intelligence Pipeline

This worker processes tasks via Celery and orchestrates the intelligence lifecycle through a strictly typed `AudioAnalysisState` LangGraph.

### 1. Profiling and Validation (`audio_profiler.py`)
- Reads metadata without loading the entire file into RAM, using lightweight wrappers around `soundfile` and `librosa`.
- Validates that the file size (`< 200MB`) and duration (`< 3 hours`) strictly match the platform's constraints.
- Emits rough estimations of the speaker count and channel configurations.

### 2. Signal Preprocessing (`preprocessor_agent.py`)
- **Normalization:** Uses `pydub` to force the audio to purely Mono, resamples to `16kHz`, and normalizes the acoustic volume to `-14 dBFS` (industry standard for speech clarity).
- **Segmentation:** Runs a fast amplitude-based Silence Detection algorithm (VAD) to split the audio and estimate rough turn-taking sequences.
- **Serialization:** Encodes the cleaned internal `.wav` immediately to `Base64` for the API.

### 3. Native Multimodal Transcription (`transcription_agent.py`)
- Forwards the `Base64` blob securely to **OpenRouter** targeting `google/gemini-2.5-flash-preview`.
- Exploits Native Audio Input functionality—meaning NO expensive cascading from ASR to NLP. The model hallucinates far less by interpreting acoustic cues directly.
- Forces the output into a strictly structured JSON containing the `raw_transcript` and granular `speaker_turns`.

### 4. Semantic Diarization & Resolution (`diarization_agent.py`)
- Transcriptions naturally produce labels like `SPEAKER_01`, `SPEAKER_02`.
- If the user provides a list of `participant_names` (e.g., `["Ahmed", "Sara"]`), this node performs contextual inference using `gemini-2.0-flash-lite`, analyzing conversation clues ("Hi Sara, how are you?") to probabilistically map `SPEAKER_01` -> `Ahmed`.

### 5. Cost-Efficient Entity Extraction (`entity_extractor.py`)
- Uses the highly economical `meta-llama/llama-3.1-8b-instruct` strictly via Text-Prompting on the resolved transcript.
- Hunts for precisely 4 classes of metadata: **Named Entities** (People, Organizations, Amounts), **Action Items**, **Discussion Topics**, and **Key Quotes**.

### 6. Synthesizer & Insight Generation (`summarizer_agent.py`)
- Aggregates the entities, topics, and transcript segments to generate an extensive `insight_report`.
- Computes an extremely condensed 3-sentence `executive_summary` suitable for dashboard rendering.

### 7. Zero-Cost RAG Evaluation (`evaluation_agent.py`)
- Evaluates the "quality" of the generated insights against the transcript chunks precisely the same way `worker-pdf` evaluates RAG retrieval.
- Computes **Utilization**, **Relevance**, and **Attribution** locally via `sentence-transformers` without invoking paid APIs.

### 8. Semantic Vector Indexer (`vector_indexer.py`)
- **Semantic Vector Storage:** Chunks every distinct speaker turn, computes 768D embeddings locally using `fastembed`, and uploads them cleanly to **Qdrant** for similarity searches.

### 9. Neo4j Graph Builder (`graph_knowledge_builder.py`)
- **Graph Topologies:** Creates `AudioSource`, `Speaker`, and `Entity` nodes in **Neo4j** connected by `[:SPEAKS_IN]` and `[:MENTIONED_IN]` edges, allowing the open intelligence federation (Nexus) to link a user speaking in a call to a commit they pushed in GitHub.

### 10. Output Assembler (`output_assembler.py`)
- Condenses the `AudioAnalysisState` safely.
- Exits the Graph, handing control back to the Celery worker (`worker.py`), which persists the payload safely into the Postgres `analysis_results` table.

---

## ⚙️ Environment Configuration

Ensure the following configuration variables are populated in your `.env`:

| Variable | Description |
|---|---|
| `REDIS_URL` | Redis instance for the Celery message broker and backend. |
| `DATABASE_URL` | PostgreSQL URL for fetching and updating Analysis Job statuses asynchronously. |
| `NEO4J_URI` | Bolt connector string to the Neo4j Graph DB deployment (`bolt://...:7687`). |
| `QDRANT_URL` | HTTP endpoint for the vector database (`http://qdrant:6333`). |
| `OPENROUTER_API_KEY` | **Crucial:** Used for routing to Gemini Flash and Llama 3 models. |

---

## 🚀 Tasks & Queues mapping

| Task | Queue | Payload |
|---|---|---|
| `app.worker.run_audio_analysis` | `pillar.audio` | `{ "job_id": "<uuid>" }` |

When a task executes effectively, it parses state metrics back into the main PostgreSQL `analysis_jobs` and `analysis_results` records, enabling synchronous UI updates on the Frontend without locking up primary API resources.
