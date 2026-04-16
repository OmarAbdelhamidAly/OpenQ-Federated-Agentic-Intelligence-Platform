<div align="center">

# 📚 Worker PDF (DocRAG Multimodal Pillar)

**Triple Synthesis Engines and Vision Decoding Matrix**

[![Python Tools](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Celery Tasks](https://img.shields.io/badge/Celery-5.4-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Gemini](https://img.shields.io/badge/Gemini-2.0--Flash%20Vision-4285F4?logo=google-gemini&logoColor=white)](https://deepmind.google/)

</div>

---

## 🎯 Overview

The `worker-pdf` service is distinctively architected for the OpenQ Multimodal platform. Built atop **Gemini 2.0 Flash Vision**, it fundamentally bypasses traditional (and heavily lossy) PyPDF text extractors by comprehending pages holistically as rendered images via Vision LLM processing.

---

## 🏗️ Architecture Design

It runs a specialized **10-node Orchestrator StateGraph**:

### Synthesis Router
Rather than treating every request uniformly, the system evaluates intent before allocating compute power:
- **`deep_vision` Synthesis Mode**: Explicitly uses Gemini 2.0 Vision modules to read charts, architecture flows, tables, and complex graphs natively without OCR middle-ware.
- **`fast_text` Synthesis Mode**: Low-latency path that routes straight against lightweight `Qdrant` text embedding chunks for fast qualitative questions.
- **`hybrid_ocr` Synthesis Mode**: Blends OCR bounding boxes with mathematical summarization.

### Anti-Hallucination Matrix
The PDF worker runs an isolated `Verifier` node. After drafting an insight report, this node interrogates the draft against the exact Qdrant source chunks pulled. If assertions are identified that have *zero* backing chunk reference, the document is forcibly injected with a high-temperature reflection fix constraint up to 2 times to correct the hallucinated figures.

---

## ⚙️ Environment Configuration

| Variable | Description |
|---|---|
| `REDIS_URL` / `DATABASE_URL` | Foundation task dispatch systems and reporting metrics. |
| `LLM_MODEL_PDF` | Explicit tuning (`google/gemini-2.0-flash-lite-001` or upgraded vision). |
| `QDRANT_URL` | For loading semantic dimensions and metadata pointers mappings. |

---

## 🚀 Tasks & Queues mapping

| Task | Queue | Target |
|---|---|---|
| `pillar_task` | `pillar.pdf` | Multimodal evaluation task orchestrator entry. |
