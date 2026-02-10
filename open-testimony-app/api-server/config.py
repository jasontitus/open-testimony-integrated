"""Configuration settings for the Open Testimony API"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    DATABASE_URL: str = "postgresql://user:pass@db:5432/opentestimony"
    
    # MinIO
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_EXTERNAL_ENDPOINT: str = "localhost/video-stream"
    MINIO_EXTERNAL_SCHEME: str = "http"  # Use "https" when behind ngrok
    MINIO_ACCESS_KEY: str = "admin"
    MINIO_SECRET_KEY: str = "supersecret"
    MINIO_BUCKET: str = "opentestimony-videos"
    MINIO_SECURE: bool = False  # Set to True for HTTPS

    # Tags
    DEFAULT_TAGS_FILE: str = "default_tags.json"

    # Auth
    JWT_SECRET_KEY: str = "change-me-in-production"
    ADMIN_USERNAME: str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_DISPLAY_NAME: str = "Admin"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
