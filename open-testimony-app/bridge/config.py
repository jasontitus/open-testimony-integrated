"""Configuration settings for the AI Search Bridge Service."""
import os


class Settings:
    # Database (shared with Open Testimony)
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql://user:pass@db:5432/opentestimony"
    )

    # MinIO (shared with Open Testimony)
    MINIO_ENDPOINT: str = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    MINIO_ACCESS_KEY: str = os.environ.get("MINIO_ACCESS_KEY", "admin")
    MINIO_SECRET_KEY: str = os.environ.get("MINIO_SECRET_KEY", "supersecret")
    MINIO_BUCKET: str = os.environ.get("MINIO_BUCKET", "opentestimony-videos")
    MINIO_SECURE: bool = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    # JWT (must match Open Testimony API)
    JWT_SECRET_KEY: str = os.environ.get(
        "JWT_SECRET_KEY", "change-me-in-production-use-a-real-secret"
    )
    JWT_ALGORITHM: str = "HS256"

    # Vision model
    # open_clip: "ViT-L-14", "ViT-B-32", etc.
    # pe_core: "PE-Core-L14-336", "PE-Core-B16-224", "PE-Core-G14-448"
    VISION_MODEL_FAMILY: str = os.environ.get("VISION_MODEL_FAMILY", "open_clip")
    VISION_MODEL_NAME: str = os.environ.get("VISION_MODEL_NAME", "ViT-L-14")
    VISION_MODEL_PRETRAINED: str = os.environ.get(
        "VISION_MODEL_PRETRAINED", "datacomp_xl_s13b_b90k"
    )
    VISION_EMBEDDING_DIM: int = int(os.environ.get("VISION_EMBEDDING_DIM", "768"))

    # Transcript model
    TRANSCRIPT_MODEL_NAME: str = os.environ.get(
        "TRANSCRIPT_MODEL_NAME", "Qwen/Qwen3-Embedding-8B"
    )
    TRANSCRIPT_EMBEDDING_DIM: int = int(
        os.environ.get("TRANSCRIPT_EMBEDDING_DIM", "4096")
    )

    # Whisper model
    WHISPER_MODEL: str = os.environ.get("WHISPER_MODEL", "base")

    # Processing
    DEVICE: str = os.environ.get("DEVICE", "cpu")
    USE_FP16: bool = os.environ.get("USE_FP16", "false").lower() == "true"
    FRAME_INTERVAL_SEC: float = float(os.environ.get("FRAME_INTERVAL_SEC", "2.0"))
    BATCH_SIZE: int = int(os.environ.get("BATCH_SIZE", "16"))
    TEMP_DIR: str = os.environ.get("TEMP_DIR", "/data/temp")

    # Worker
    WORKER_POLL_INTERVAL: int = int(os.environ.get("WORKER_POLL_INTERVAL", "10"))

    # Open Testimony API (for metadata enrichment)
    OT_API_URL: str = os.environ.get("OT_API_URL", "http://api:8000")


settings = Settings()
