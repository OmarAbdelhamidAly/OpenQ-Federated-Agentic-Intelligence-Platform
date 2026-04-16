<div align="center">

# 🎧 Worker Audio (Acoustic Multimodal Pillar)

**Direct Transcription, Diarization, and Graph Ingestion**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Gemini 1.5](https://img.shields.io/badge/Gemini-1.5--Flash-4285F4?logo=google-gemini&logoColor=white)](https://deepmind.google/)

</div>

---

## 🎯 Overview

The `worker-audio` service allows OpenQ to ingest `.wav`, `.mp3`, and `.m4a` files intrinsically securely. Driven largely by Gemini 1.5 Flash capabilities, this specialized module circumvents outdated legacy NLP processing and relies solely on advanced Multimodal capabilities directly on raw bytes.

---

## 🏗️ Architecture Design

Unlike tabular workers that use cyclic self-healing grids, acoustic metadata extraction implies a **Direct task architecture**:

- **Speech-to-Text Transcription**: Rapid decoding of linguistic patterns and formatting.
- **Speaker Diarization**: Explicitly isolates distinct voice patterns and segments transcriptions logically by "Speaker A", "Speaker B", granting critical contextual logic for analytics.
- **Cross-Pillar Neo4j Sync**: Like all multimodal components in OpenQ, audio endpoints pull Named Entities (e.g., Organizations, Names, Dates, Products) from audio and systematically ingest these Entity clusters precisely into the `Neo4j` knowledge graph. 
  - This allows a user to query: *"Did the CEO mention the 'Project X' component mapped in my source codebase?"* natively via the Nexus module.

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `REDIS_URL` | Baseline task queuing backend. |
| `DATABASE_URL` | Status flag operations (`done`, `error`) routing logic. |
| `LLM_MODEL_FAST` | Optimized metadata extraction LLM (e.g. `meta-llama/llama-3.2-3b-instruct` or Gemini 1.5 variants). |
| `NEO4J_URI` | Target graph database for Named Entity Recognition syncs. |

---

## 🚀 Tasks Handled

| Task | Queue | Format Expected |
|---|---|---|
| `process_audio_ingest` | `pillar.audio` | Bytes payload metadata with DB reference ID. |
