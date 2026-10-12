from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    display_timezone: str = "Asia/Kolkata"
    database_url: str = "sqlite:///./data/signal.db"
    data_dir: Path = Path("./data")
    llm_provider: Literal["openai", "gemini", "nvidia"] = "openai"
    openai_api_key: str = Field(default="", repr=False)
    openai_model_research: str = ""
    openai_model_extract: str = ""
    nvidia_api_key: str = Field(default="", repr=False)
    nvidia_model_research: str = ""
    nvidia_model_extract: str = ""
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model_research: str = ""
    gemini_model_extract: str = ""
    gemini_thinking_level: Literal["minimal", "low", "medium", "high"] = "low"
    gemini_max_attempts: int = Field(default=2, ge=1, le=3)
    search_provider: str = "tavily"
    free_services_only: bool = False
    tavily_api_key: str = Field(default="", repr=False)
    tavily_search_depth: Literal["basic", "advanced"] = "basic"
    research_mode: str = "live"
    max_run_seconds: int = 420
    max_search_calls: int = 30
    max_fetch_documents: int = 30
    max_model_calls: int = 50
    max_ocr_pages: int = 8
    max_fetch_concurrency: int = 3
    max_active_runs: int = 1
    max_input_tokens: int = 150000
    max_output_tokens: int = 20000
    max_model_output_tokens_per_call: int = Field(default=8192, ge=256, le=65536)
    max_run_cost_usd: float = 5.0
    search_usd_per_credit: float | None = None
    model_rate_card_path: Path = Path("./config/model-rates.json")
    source_request_timeout_seconds: int = 25
    pdf_parse_timeout_seconds: float = Field(default=90, gt=0, le=300)
    model_request_timeout_seconds: float = Field(default=90, gt=0, le=300)
    max_source_bytes: int = 25_000_000
    allow_fixture_provider: bool = False
    allow_unknown_cost: bool = False
    auto_start_worker: bool = False
    pdftoppm_path: str = "pdftoppm"
    tesseract_path: str = "tesseract"

    def model_for_role(self, role: str) -> str:
        if role not in {"extract", "research"}:
            raise ValueError(f"unknown model role: {role}")
        return getattr(self, f"{self.llm_provider}_model_{role}")

    @property
    def llm_configured(self) -> bool:
        return bool(getattr(self, f"{self.llm_provider}_api_key") and
                    self.model_for_role("research") and self.model_for_role("extract"))

    @property
    def sqlite_path(self) -> Path | None:
        if self.database_url.startswith("sqlite"):
            return Path(self.database_url.rsplit("/", 1)[-1])
        return None

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        for name in ("raw", "parsed", "exports"):
            (self.data_dir / name).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
