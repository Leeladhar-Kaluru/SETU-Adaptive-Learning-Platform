import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    APP_NAME: str = "SETU"
    APP_ENV: str = "local"
    SETU_TEST_AUTH: bool = False
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    FRONTEND_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    DATABASE_URL: str
    # Supabase's session-mode pooler caps the whole project at 15 clients, so
    # each process must stay small. API gets 4+2, the worker is started with
    # POOL_SIZE=2 / MAX_OVERFLOW=1 via environment.
    POOL_SIZE: int = 4
    MAX_OVERFLOW: int = 2
    POOL_TIMEOUT: int = 30
    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""
    SUPABASE_SECRET_KEY: str = ""
    
    # Storage settings
    STORAGE_BACKEND: str = "supabase"  # "supabase" or "local" (local is refused outside local/test)
    LOCAL_STORAGE_DIR: str = "local_storage"
    STORAGE_BUCKET_DOCUMENTS: str = "setu-documents"
    MAX_UPLOAD_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB — full textbooks exceed 50 MB
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "docx", "pptx", "txt", "md", "jpg", "jpeg", "png"]
    
    # AI and Embeddings configuration
    ENABLE_REMOTE_AI: bool = False
    LLM_BASE_URL: str = "http://127.0.0.1:1234/v1"
    LLM_MODEL: str = "google/gemma-4-e4b"
    EMBEDDING_MODEL: str = "text-embedding-nomic-embed-text-v1.5"
    EMBEDDING_DIMENSION: int = 768

    model_config = SettingsConfigDict(
        env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.FRONTEND_ORIGINS.split(",") if origin.strip()]

settings = Settings()

