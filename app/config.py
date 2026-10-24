"""Application Configuration & Environment Settings.

Validates application parameters using Pydantic Settings:
- Server settings (host, port, debug mode)
- SQLite database connection URL
- Storage directories (uploads, raw, processed, Qdrant index)
- Security bounds (upload size, retry limits, concurrency limits)
- SEC EDGAR User-Agent compliance
- Optional LLM provider configuration
"""

from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings schema loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application & Environment
    app_name: str = Field(default="Trustworthy Multi-Agent Financial Research System", alias="APP_NAME")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    host: str = Field(default="127.0.0.1", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    frontend_cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="FRONTEND_CORS_ORIGINS",
    )

    # Persistence & Storage
    database_url: str = Field(
        default="sqlite:///./data/financial_research.db",
        alias="DATABASE_URL",
    )
    upload_dir: Path = Field(default=Path("./data/uploads"), alias="UPLOAD_DIR")
    raw_dir: Path = Field(default=Path("./data/raw"), alias="RAW_DIR")
    processed_dir: Path = Field(default=Path("./data/processed"), alias="PROCESSED_DIR")
    qdrant_path: Path = Field(default=Path("./data/qdrant"), alias="QDRANT_PATH")

    # Limits and Safeguards
    max_upload_mb: int = Field(default=25, alias="MAX_UPLOAD_MB")
    max_research_retries: int = Field(default=3, alias="MAX_RESEARCH_RETRIES")
    max_concurrent_runs: int = Field(default=2, alias="MAX_CONCURRENT_RUNS")

    # Regulatory Connectors
    sec_user_agent: str = Field(
        default="FinancialResearchSystem user@example.com",
        alias="SEC_USER_AGENT",
    )

    # Optional Model Providers (Free-first: not mandatory for startup or tests)
    llm_provider: str = Field(default="google_genai", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gemini-2.5-pro", alias="LLM_MODEL")
    llm_api_key: Optional[str] = Field(default=None, alias="LLM_API_KEY")

    def get_cors_origins(self) -> List[str]:
        """Parse comma-separated CORS origin string into a clean list."""
        if not self.frontend_cors_origins:
            return ["*"]
        return [origin.strip() for origin in self.frontend_cors_origins.split(",") if origin.strip()]

    def ensure_directories(self) -> None:
        """Create required persistent storage directories safely."""
        for path in (self.upload_dir, self.raw_dir, self.processed_dir, self.qdrant_path):
            path.mkdir(parents=True, exist_ok=True)


# Global singleton instance
settings = Settings()
