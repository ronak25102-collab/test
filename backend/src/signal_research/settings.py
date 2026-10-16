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
    llm_provider: Literal["openai", "gemini", "nvidia", "codecraft"] = "openai"
    codecraft_api_key: str = Field(default="", repr=False)
    codecraft_secondary_api_keys: list[str] = Field(default_factory=list, repr=False, exclude=True, max_length=5)
    codecraft_nvidia_fallback: bool = False
    codecraft_key_routing: Literal['sequential', 'balanced'] = 'sequential'
    max_model_concurrency: int = Field(default=3, ge=1, le=6)
    max_research_agents: int = Field(default=3, ge=1, le=6)
    nvidia_planning: bool = False
    codecraft_model_research: str = ""
    codecraft_model_extract: str = ""
    openai_api_key: str = Field(default="", repr=False)
    openai_model_research: str = ""
    openai_model_extract: str = ""
    nvidia_api_key: str = Field(default="", repr=False)
    nvidia_model_research: str = ""
    nvidia_model_extract: str = ""
    nvidia_response_format: Literal['json_schema', 'json_object'] = 'json_schema'
    nvidia_reasoning_budget: int | None = Field(default=None, ge=0, le=32768)
    stage_output_tokens: dict[str, int] = Field(default_factory=dict)
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
    cold_start: bool = False
    max_run_seconds: int = 300
    demo_target_seconds: int = Field(default=300, ge=30, le=300)
    stage_request_seconds: dict[str, float] = Field(default_factory=lambda: {'extracting': 55, 'normalizing': 55, 'hypothesizing': 35, 'challenging': 35, 'composing': 40, 'verifying': 40})
    max_search_calls: int = 30
    max_fetch_documents: int = 30
    max_model_calls: int = 50
    max_ocr_pages: int = 8
    max_fetch_concurrency: int = 3
    max_active_runs: int = 1
    max_input_tokens: int = 150000
    max_output_tokens: int = 20000
    max_model_output_tokens_per_call: int = Field(default=16384, ge=256, le=65536)
    max_run_cost_usd: float = 5.0
    search_usd_per_credit: float | None = None
    model_rate_card_path: Path = Path("./config/model-rates.json")
    source_request_timeout_seconds: int = 25
    pdf_parse_timeout_seconds: float = Field(default=90, gt=0, le=300)
    model_request_timeout_seconds: float = Field(default=90, gt=0, le=900)
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

    def model_routes(self):
        """Ordered, deduplicated credentials; public route names never contain keys."""
        if self.llm_provider != "codecraft":
            return [("primary", self)]
        keys = list(dict.fromkeys(key.strip() for key in
                    [self.codecraft_api_key, *self.codecraft_secondary_api_keys] if key.strip()))
        routes = [(f"codecraft:{index}", self.model_copy(update={"codecraft_api_key": key}))
                  for index, key in enumerate(keys)]
        if self.codecraft_nvidia_fallback:
            routes.append(("nvidia", self.model_copy(update={"llm_provider": "nvidia"})))
        return routes

    def routes_for_stage(self, role: str, stage: str):
        """Hybrid routing is explicit; final review uses only authorized fallback routes."""
        if self.nvidia_planning and (role == 'extract' or stage in {'planning', 'hypothesizing'}):
            return [('nvidia-planning', self.model_copy(update={'llm_provider': 'nvidia'}))]
        return self.model_routes()

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
