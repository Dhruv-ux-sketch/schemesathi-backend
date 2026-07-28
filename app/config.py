"""
Central configuration. Reads from .env at project root.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
   # LLM
    LLM_PROVIDER: str = "none"          # "openai" | "anthropic" | "gemini" | "none"
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Embeddings (local, free, no API key)
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Vector store
    CHROMA_DIR: str = "./data/chroma_db"
    CHROMA_COLLECTION: str = "government_schemes"

    # Retrieval
    TOP_K: int = 4
    MIN_RELEVANCE_SCORE: float = 0.35
    CHUNK_SIZE: int = 800        # characters per chunk
    CHUNK_OVERLAP: int = 120

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # Database (Postgres - recommended free host: neon.tech, no credit card needed)
    DATABASE_URL: str = "sqlite:///./data/schemesathi.db"

    # Auth
    JWT_SECRET: str = "change-this-to-a-long-random-string-before-deploying"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # The account with this email gets admin access (upload/delete schemes).
    # Set this to your own account's email before deploying.
    ADMIN_EMAIL: str = ""

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


settings = Settings()
