from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    ENV: str = "development"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/analyst_agent"
    REDIS_URL: str = "redis://redis:6379/0"
    
    # Vision Settings
    SNAPSHOT_INTERVAL_SECONDS: int = 10
    FACE_SIMILARITY_THRESHOLD: float = 0.6
    VISION_MODEL_YOLO: str = "yolov8n.pt" # Using nano for speed

settings = Settings()
