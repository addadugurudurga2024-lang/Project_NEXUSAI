# pyright: ignore [reportMissingImports]
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "nexusai"
    jwt_secret_key: str = "nexusai-dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    ai_provider: str = "openai"
    ai_api_key: Optional[str] = ""
    ai_model: str = "gpt-4o-mini"
    ai_base_url: str = "https://api.openai.com/v1"
    backend_port: int = 8000
    upload_dir: str = "../uploads"
    max_upload_size_mb: int = 25
    seed_admin_password: Optional[str] = ""
    pm_team_capacity: int = 18

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
