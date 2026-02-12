from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://fantasy:fantasysecret@localhost:5433/fantasy_skiing"
    database_url_sync: str = "postgresql://fantasy:fantasysecret@localhost:5433/fantasy_skiing"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    admin_username: str = "admin"
    admin_password: str = "admin123"

    class Config:
        env_file = ".env"


settings = Settings()
