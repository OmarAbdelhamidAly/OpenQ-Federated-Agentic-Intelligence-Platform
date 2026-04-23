# 👁️ OpenQ Worker Vision Service

## 📌 Overview
The **Worker Vision Service** is the "Visual Intelligence" pillar of the OpenQ platform. It provides non-intrusive, privacy-aware employee tracking and engagement analysis using Computer Vision. 

Instead of traditional 30fps streaming, this service uses a **10-second sampling strategy** to balance computational efficiency with high-quality strategic insights.

---

## 🏗️ Architecture: Clean & Decoupled
This service follows the **Clean Architecture** pattern to ensure that the AI logic is independent of the database and external frameworks.

### 📂 Directory Structure & File Explanation

#### 🌍 `app/domain/` (The Heart)
*   **`vision/entities.py`**: Defines the "Source of Truth" for vision data. It contains `VisionState` (the pipeline's shared memory) and `DetectionEntity`. No external libraries (like OpenCV) touch this layer.

#### 🛠️ `app/infrastructure/` (The Tools)
*   **`ai/yolo_engine.py`**: Implementation of **YOLOv11** for person and object detection. It answers the question: *"Is there a human at the desk? Are they using a phone?"*
*   **`ai/face_engine.py`**: Implementation of **FaceNet (via DeepFace)** for identity verification. It answers: *"Who is this person specifically?"*
*   **`database/repository.py`**: The Data Access Layer. It abstracts complex SQL queries into simple methods like `get_all_cameras()` or `save_logs()`.
*   **`database.py`**: Sets up the asynchronous SQLAlchemy engine and session factory.

#### ⚙️ `app/use_cases/` (The Logic)
*   **`process_vision_frame.py`**: The orchestrator. It receives a raw frame, passes it to the YOLO engine for detection, then to the Face engine for identification, and finally calculates the `engagement_score`.

#### 📊 `app/models/` (The Persistence)
*   **`vision.py`**: Defines the PostgreSQL tables:
    *   `VisionCamera`: Metadata for RTSP streams and their room locations.
    *   `VisionFaceEmbedding`: 128/512-dimension vectors for known employees.
    *   `VisionLog`: The historical timeline of activity.

#### 🔄 `app/worker.py` (The Engine)
*   The background loop that runs every 10 seconds. It handles camera polling, frame capture, and triggers the analysis pipeline.

#### 🚀 `app/main.py` (The Entry Point)
*   The FastAPI application. It handles the lifecycle (lifespan) of the service, synchronizes the database schema on startup, and launches the background worker.

---

## 💡 The Core Idea: "Moving Business Numbers"
As discussed in our strategy, this service is designed to move real business KPIs:
1.  **Operational Efficiency**: Identifying office occupancy vs. meeting room bookings.
2.  **Productivity Baseline**: Establishing a baseline of focused work hours vs. distractions.
3.  **Safety & Security**: Instant identification of unauthorized persons in restricted zones.

---

## 🛠️ Tech Stack
- **Framework**: FastAPI (Async)
- **Object Detection**: Ultralytics YOLOv11
- **Face Recognition**: DeepFace (FaceNet)
- **Database**: PostgreSQL (SQLAlchemy 2.0)
- **Real-time Messaging**: Redis Pub/Sub
- **Processing**: OpenCV

---

## 🔧 How to Run
The service is fully integrated into the main `docker-compose.yml`. 
To build and run:
```bash
docker-compose up --build worker-vision
```
