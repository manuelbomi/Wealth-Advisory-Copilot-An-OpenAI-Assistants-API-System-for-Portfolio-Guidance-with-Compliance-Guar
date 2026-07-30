"""Application configuration.

Design decision: all runtime configuration is loaded via `pydantic-settings` from
environment variables (and a local `.env` file for developer convenience). We never
hardcode secrets or environment-specific values in source. Secrets such as
`OPENAI_API_KEY` are typed as `SecretStr` so they are never accidentally rendered in
logs, tracebacks, or `repr()` output.

If `OPENAI_API_KEY` is not set, the application runs in fully offline "mock" mode:
`app.infrastructure.client_factory` swaps in `MockAssistantsClient`, which
deterministically simulates the OpenAI Assistants API thread/run/tool-call lifecycle.
This lets a reviewer clone the repo and run everything -- app, tests, CI -- with zero
paid API keys.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root, used to resolve default paths (fund fact sheets, audit log) so the
# app behaves the same regardless of the process's current working directory.
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Centralized, validated application settings.

    Every field has a safe local-dev default so `make run` / `pytest` work out of the
    box without any `.env` file. Production deployments override via real environment
    variables (see deploy/k8s/configmap.yaml and deploy/OPENSHIFT.md).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Identity / metadata ---------------------------------------------------
    app_name: str = "wealth-advisory-copilot"
    environment: str = Field(default="local", description="local | ci | staging | production")

    # --- OpenAI Assistants API ---------------------------------------------------
    # Absence of this key is the explicit signal to run in offline mock mode.
    openai_api_key: SecretStr | None = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini", description="Model used to create the Assistant")
    openai_assistant_name: str = "Northbridge Wealth Advisory Copilot"
    openai_request_timeout_seconds: float = 30.0
    openai_max_retries: int = 4

    # --- Circuit breaker (wraps outbound OpenAI calls) ---------------------------
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_reset_seconds: float = 30.0

    # --- Data paths ---------------------------------------------------------------
    fund_factsheets_dir: Path = _REPO_ROOT / "data" / "fund_factsheets"
    audit_log_path: Path = _REPO_ROOT / "logs" / "audit_log.jsonl"

    # --- Server ---------------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000
    cors_allow_origins: list[str] = Field(default_factory=lambda: ["*"])

    # --- Logging ------------------------------------------------------------------
    log_level: str = "INFO"
    log_json: bool = True

    @property
    def is_mock_mode(self) -> bool:
        """True when no OpenAI API key is configured -> use MockAssistantsClient."""
        return self.openai_api_key is None or not self.openai_api_key.get_secret_value().strip()


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance.

    Cached with `lru_cache` so environment/`.env` parsing happens once per process,
    not on every request -- a small but real perf/consistency win, and it gives tests
    a single seam (`get_settings.cache_clear()`) to reset configuration between cases.
    """
    return Settings()
