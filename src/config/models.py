"""Config models and loader.

This module defines Pydantic models for file- and environment-based
configuration. JSON parsing prefers `orjson` when available for speed and
lower memory usage, but intentionally falls back to the Python standard
library's `json` module. Keeping `orjson` optional improves portability in
diverse environments (e.g., minimal CI images, dev shells) while retaining
performance benefits where wheels are available.
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    import orjson as _orjson_mod  # type: ignore[assignment]
except ImportError:  # pragma: no cover - optional dependency
    _orjson_mod = None  # type: ignore[assignment]
    _loads_orjson: Optional[Callable[[bytes], Any]] = None
else:

    def _loads_orjson(buf: bytes) -> Any:
        loader = getattr(_orjson_mod, "loads")  # type: ignore[assignment]
        return loader(buf)


from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SourceConfig(BaseModel):
    """Configuration for a single Source MCP.

    Attributes
    ----------
    endpoint: str
        MCP endpoint URL for the source implementation.
    api_key: Optional[str]
        Optional bearer token used to authenticate to the source.
    type: str
        Source type identifier (e.g., "horreum").
    timeout_seconds: int
        HTTP request timeout in seconds for adapter operations.
    """

    endpoint: str = Field(..., description="MCP endpoint URL or stdio command")
    api_key: Optional[str] = Field(None, description="Authentication token")
    type: str = Field("horreum-mcp-http", description="Source type identifier")
    timeout_seconds: int = Field(30, ge=1)
    max_retries: int = Field(1, ge=0, description="Number of retry attempts")
    backoff_initial_ms: int = Field(
        200, ge=0, description="Initial backoff in milliseconds"
    )
    backoff_multiplier: float = Field(
        2.0, ge=1.0, description="Backoff multiplier per attempt"
    )
    # For stdio bridge
    stdio_args: Optional[list[str]] = Field(
        default=None, description="Arguments for stdio command (bridge mode)"
    )
    env: Optional[Dict[str, str]] = Field(
        default=None, description="Environment variables for stdio process"
    )


class AppConfig(BaseModel):
    """Top-level application configuration.

    Attributes
    ----------
    sources: Dict[str, SourceConfig]
        Mapping from logical `source_id` to connection settings.
    enabled_plugins: Dict[str, bool]
        Feature flags for dataset-type plugins by identifier.
    """

    sources: Dict[str, SourceConfig] = Field(default_factory=dict)
    enabled_plugins: Dict[str, bool] = Field(default_factory=dict)

    @staticmethod
    def load(path: Path) -> "AppConfig":
        """Load application config from a JSON file.

        Rationale for optional `orjson`:
        - Performance: `orjson` is significantly faster and more memory
          efficient for large JSONs.
        - Portability: Falling back to `json` avoids making `orjson` a hard
          requirement in constrained environments (e.g., uncommon platforms,
          sandboxed CI runners) while keeping the code runnable.
        - Developer experience: Reduces install friction when wheels are not
          readily available.
        """
        raw = path.read_bytes()
        if _loads_orjson is not None:
            data = _loads_orjson(raw)
        else:
            data = _json.loads(raw.decode("utf-8"))
        return AppConfig.model_validate(data)


class EnvSettings(BaseSettings):
    """Environment-driven settings and .env support.

    Attributes
    ----------
    log_level: str
        Logging level name (e.g., "DEBUG", "INFO"). Defaults to "INFO".
    otlp_endpoint: Optional[str]
        Optional OpenTelemetry OTLP collector endpoint.
    LLM_PROVIDER: Optional[str]
        LLM provider name ("gemini", "openai", "anthropic", "azure"). Optional.
    LLM_API_KEY: Optional[str]
        API key for LLM provider authentication. Required if LLM_PROVIDER is set.
    LLM_MODEL: Optional[str]
        LLM model name (e.g., "gemini-1.5-pro", "gpt-4"). Required if LLM_PROVIDER set.
    LLM_GEMINI_ENDPOINT: Optional[str]
        Custom Gemini endpoint URL for Vertex AI / corporate instances. Optional.
    LLM_GEMINI_PROJECT: Optional[str]
        Google Cloud project ID for Vertex AI billing. Optional.
    LLM_TEMPERATURE: float
        LLM temperature for response generation (0.0-1.0). Defaults to 0.1.
    LLM_MAX_TOKENS: int
        Maximum tokens for LLM responses. Defaults to 4096.
    LLM_MAX_ITERATIONS: int
        Maximum LLM orchestration iterations for complex queries. Defaults to 10.
        Increase for queries requiring multiple tool calls (e.g., 20-30).
    """

    model_config = SettingsConfigDict(env_file=".env", env_prefix="DOMAIN_MCP_")

    log_level: str = Field("INFO")
    otlp_endpoint: Optional[str] = None

    # LLM configuration (Phase 6.1)
    LLM_PROVIDER: Optional[str] = Field(
        None,
        description="LLM provider: gemini, openai, anthropic, or azure",
    )
    LLM_API_KEY: Optional[str] = Field(
        None,
        description="API key for LLM provider authentication",
    )
    LLM_MODEL: Optional[str] = Field(
        None,
        description="LLM model name (e.g., gemini-1.5-pro, gpt-4)",
    )
    LLM_GEMINI_ENDPOINT: Optional[str] = Field(
        None,
        description="Custom Gemini endpoint for Vertex AI / corporate instances",
    )
    LLM_GEMINI_PROJECT: Optional[str] = Field(
        None,
        description="Google Cloud project ID for Vertex AI billing",
    )
    LLM_TEMPERATURE: float = Field(
        0.1,
        ge=0.0,
        le=1.0,
        description="LLM temperature for response generation (0.0-1.0)",
    )
    LLM_MAX_TOKENS: int = Field(
        4096,
        ge=1,
        le=32768,
        description="Maximum tokens for LLM responses",
    )
    LLM_MAX_ITERATIONS: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum LLM orchestration iterations for complex queries",
    )

    # Rate Limiting Configuration (Phase 6.3)
    RATE_LIMIT_ENABLED: bool = Field(
        True,
        description="Enable rate limiting for /api/query endpoint",
    )
    RATE_LIMIT_REQUESTS_PER_HOUR: int = Field(
        100,
        ge=1,
        description="Maximum requests per client per hour",
    )
    RATE_LIMIT_TOKENS_PER_HOUR: int = Field(
        100000,
        ge=1000,
        description="Maximum tokens per client per hour",
    )
    RATE_LIMIT_ADMIN_KEY: Optional[str] = Field(
        None,
        description="Admin key to bypass rate limits (for testing/debugging)",
    )

    # Query Input Validation (Phase 6.3)
    QUERY_MAX_LENGTH: int = Field(
        2000,
        ge=100,
        le=10000,
        description="Maximum allowed length for natural language queries",
    )
