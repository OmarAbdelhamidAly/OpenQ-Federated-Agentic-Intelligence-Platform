<div align="center">

# 🖼️ Worker Image & 🎬 Worker Video (Vision Pillars)

**Deep Object Recognition, Scene Geometry, & Entity Linking**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Gemini Vision](https://img.shields.io/badge/Gemini-Multimodal-4285F4?logo=google-gemini&logoColor=white)](https://deepmind.google/)
[![Neo4j](https://img.shields.io/badge/Neo4j-Entity%20Graph-018BFF?logo=neo4j&logoColor=white)](#)

</div>

---

## 🎯 Overview

The OpenQ platform supports dense raw pixel inputs handled by `worker-image` and `worker-video`. These independent microservices tap directly into the latest Gemini Vision modality architectures to abstract high-dimensional optical patterns down into highly relational knowledge graph components.

---

## 🏗️ Architecture Design

Both structures rely on asynchronous **Direct Task Architecture** logic workflows executed over Celery endpoints immediately after static file ingestion via `api`.

- **Scene Content Extraction**: Operates native object-tagging arrays, translating dense image geometries, frame segmentation sequences, and scene interactions into precise analytical text tokens.
- **Time-coded Entity Ingestion (Video)**: For video buffers specifically, extraction relies heavily on mapped time codes, enabling semantic querying across timestamps in long-form media.
- **Neo4j Graph Synchronization**: Detected physical objects, identified faces/products, and structural texts are encoded recursively directly into the underlying `Neo4j` graph database core. 
- *When combined with the `Nexus` layer, users can prompt queries crossing boundaries between PDF textual policies and Video evidence organically.*

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `REDIS_URL` | Task dispatch routing endpoint. |
| `DATABASE_URL` | Output insight mapping connection string. |
| `LLM_MODEL_VISION` | Baseline model (e.g. `meta-llama/llama-3.2-11b-vision-instruct` or OpenRouter Gemini mapping). |
| `NEO4J_URI` | Core structural endpoint for the extracted object matrices. |

---

## 🚀 Queues Mapped

| Worker Service | Execution Queue | Format Support Matrix |
|---|---|---|
| `worker-image` | `pillar.image` | `.jpeg`, `.png`, `.webp`, `.bmp`, `.tiff` |
| `worker-video` | `pillar.video` | `.mp4`, `.mkv`, `.mov` |
