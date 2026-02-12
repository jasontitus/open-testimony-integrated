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
    # hf_siglip: "google/siglip2-so400m-patch16-naflex" (NAFlex, native aspect ratio)
    # open_clip: "ViT-SO400M-14-SigLIP2-378", "ViT-L-14", "ViT-bigG-14", etc.
    # pe_core: "PE-Core-L14-336", "PE-Core-B16-224", "PE-Core-G14-448"
    VISION_MODEL_FAMILY: str = os.environ.get("VISION_MODEL_FAMILY", "hf_siglip")
    VISION_MODEL_NAME: str = os.environ.get("VISION_MODEL_NAME", "google/siglip2-so400m-patch16-naflex")
    VISION_MODEL_PRETRAINED: str = os.environ.get(
        "VISION_MODEL_PRETRAINED", "webli"
    )
    VISION_EMBEDDING_DIM: int = int(os.environ.get("VISION_EMBEDDING_DIM", "1152"))

    # Caption provider: "gemini" for Gemini API, "local" for Qwen3-VL
    CAPTION_PROVIDER: str = os.environ.get("CAPTION_PROVIDER", "gemini")
    GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
    CAPTION_MODEL_NAME: str = os.environ.get(
        "CAPTION_MODEL_NAME", "gemini-3-flash-preview"
    )
    CAPTION_ENABLED: bool = os.environ.get("CAPTION_ENABLED", "true").lower() == "true"
    CAPTION_MAX_TOKENS: int = int(os.environ.get("CAPTION_MAX_TOKENS", "256"))
    CAPTION_BATCH_SIZE: int = int(os.environ.get("CAPTION_BATCH_SIZE", "1"))
    CAPTION_PROMPT: str = os.environ.get(
        "CAPTION_PROMPT",
        "Describe this image in detail, including all people, their physical actions, "
        "body positions, objects they are holding or carrying, and any physical "
        "interactions between people.",
    )

    # Transcript model
    TRANSCRIPT_MODEL_NAME: str = os.environ.get(
        "TRANSCRIPT_MODEL_NAME", "Qwen/Qwen3-Embedding-8B"
    )
    TRANSCRIPT_EMBEDDING_DIM: int = int(
        os.environ.get("TRANSCRIPT_EMBEDDING_DIM", "4096")
    )

    # Whisper model
    WHISPER_MODEL: str = os.environ.get("WHISPER_MODEL", "large-v3")

    # Video clip understanding (overlapping temporal windows)
    # Enable clip-level indexing for action/motion detection
    CLIP_ENABLED: bool = os.environ.get("CLIP_ENABLED", "true").lower() == "true"
    # Number of frames per clip window
    CLIP_WINDOW_FRAMES: int = int(os.environ.get("CLIP_WINDOW_FRAMES", "16"))
    # How many frames to slide forward between windows (overlap = window - stride)
    CLIP_WINDOW_STRIDE: int = int(os.environ.get("CLIP_WINDOW_STRIDE", "8"))
    # FPS for clip frame extraction (higher than FRAME_INTERVAL_SEC for temporal detail)
    CLIP_FPS: float = float(os.environ.get("CLIP_FPS", "4.0"))
    # Prompt for temporal action captioning (sent with multi-frame sequences to Gemini)
    CLIP_ACTION_PROMPT: str = os.environ.get(
        "CLIP_ACTION_PROMPT",
        "These images are consecutive frames from a video clip spanning a few seconds. "
        "Describe the physical ACTIONS and MOTION happening across these frames. "
        "Focus specifically on: body movements, physical interactions between people "
        "(pushing, grabbing, striking, restraining, choking), use of force, "
        "aggressive gestures, people falling or being thrown, and any rapid changes in posture. "
        "If no significant action is visible, say 'no significant action'. "
        "Be specific about who is doing what to whom.",
    )

    # Processing
    DEVICE: str = os.environ.get("DEVICE", "cpu")
    USE_FP16: bool = os.environ.get("USE_FP16", "false").lower() == "true"
    FRAME_INTERVAL_SEC: float = float(os.environ.get("FRAME_INTERVAL_SEC", "2.0"))
    BATCH_SIZE: int = int(os.environ.get("BATCH_SIZE", "16"))
    TEMP_DIR: str = os.environ.get("TEMP_DIR", "/data/temp")
    THUMBNAIL_DIR: str = os.environ.get("THUMBNAIL_DIR", "/data/thumbnails")

    # Worker
    WORKER_POLL_INTERVAL: int = int(os.environ.get("WORKER_POLL_INTERVAL", "10"))

    # Open Testimony API (for metadata enrichment)
    OT_API_URL: str = os.environ.get("OT_API_URL", "http://api:8000")


settings = Settings()
