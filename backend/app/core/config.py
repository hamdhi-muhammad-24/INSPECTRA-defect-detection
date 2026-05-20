from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM — Groq
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.1-8b-instant"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION_NAME: str = "inspectra_rag_documents"

    # Paths (relative to backend/ working directory)
    DATASET_PATH: str = "../data/mvtec_ad"
    RAG_DOCS_PATH: str = "../data/rag_documents"
    MODEL_DIR: str = "../models/trained"
    REPORTS_DIR: str = "../reports/generated_reports"

    # Database
    DATABASE_URL: str = "sqlite:///./inspectra.db"

    # App
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def groq_configured(self) -> bool:
        return bool(self.GROQ_API_KEY and self.GROQ_API_KEY != "your_groq_api_key_here")


settings = Settings()
