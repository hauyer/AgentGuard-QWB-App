"""Application configuration for the AgentGuard-QWB-App BFF.

The BFF is the only component allowed to talk to AgentGuard. The upstream base
URL is fixed server-side; the frontend can never influence it (SSRF guard).

Security posture (B9): configuration fails closed. Enabling authentication
without APP_SECRET_KEY, or selecting the production environment without
authentication and a strong secret, is a startup error - never a silent
fallback to a fixed development key.
"""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

APP_ENVIRONMENTS = {"development", "demo", "production"}


class Settings(BaseSettings):
    """Server-side configuration. Values come from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- AgentGuard upstream (fixed server-side) ---
    agentguard_base_url: str = "http://127.0.0.1:8000"
    agentguard_api_token: str | None = None
    agentguard_operator_api_token: str | None = None
    agentguard_api_timeout: float = 15.0

    # --- BFF application ---
    app_host: str = "127.0.0.1"
    app_port: int = 8001
    app_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    app_data_mode: str = ""
    database_url: str | None = None
    demo_fixtures_dir: str = ""
    # development | demo | production. Production enforces auth + secret key.
    app_env: str = "development"

    # --- application auth (B8, hardened in B9) ---
    # auth_enabled=false grants an implicit local admin session for development
    # only; production must set AUTH_ENABLED=true and a strong APP_SECRET_KEY
    # (validated at startup, fail closed).
    auth_enabled: bool = False
    app_secret_key: str = ""
    # Hardcoded demo accounts are available only in development/demo envs.
    # Explicitly force-enable with AUTH_DEMO_USERS_ENABLED=true at your own risk;
    # production ignores this flag and always rejects demo credentials.
    auth_demo_users_enabled: bool | None = None
    session_cookie_name: str = "qwb_session"
    csrf_cookie_name: str = "qwb_csrf"
    session_max_age_seconds: int = 8 * 60 * 60
    # Set SESSION_COOKIE_SECURE=true when serving over HTTPS (reverse proxy).
    # The flag is off by default so local HTTP development works out of the box.
    session_cookie_secure: bool = False

    @field_validator("agentguard_base_url")
    @classmethod
    def validate_agentguard_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("AGENTGUARD_BASE_URL contains an invalid port") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or (port is not None and not 1 <= port <= 65535)
        ):
            raise ValueError(
                "AGENTGUARD_BASE_URL must be an HTTP(S) origin without credentials, path, query, or fragment"
            )
        return value.rstrip("/") or value

    @field_validator("agentguard_api_timeout")
    @classmethod
    def validate_timeout(cls, value: float) -> float:
        if not 0 < value <= 120:
            raise ValueError("AGENTGUARD_API_TIMEOUT must be in the range (0, 120]")
        return value

    @field_validator("app_cors_origins")
    @classmethod
    def validate_cors_origins(cls, value: str) -> str:
        origins = [origin.strip() for origin in value.split(",") if origin.strip()]
        for origin in origins:
            if origin == "*":
                raise ValueError("APP_CORS_ORIGINS must not contain a wildcard origin")
        return ",".join(origins)

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in APP_ENVIRONMENTS:
            raise ValueError(f"APP_ENV must be one of {sorted(APP_ENVIRONMENTS)}")
        return normalized

    @field_validator("auth_demo_users_enabled", mode="before")
    @classmethod
    def empty_demo_flag_is_none(cls, value: object) -> object:
        # An unset/empty env var must mean "not explicitly configured".
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def validate_security_posture(self) -> Settings:
        # Fail closed (B9-1): no fixed fallback secret. Enabling auth without a
        # configured key must abort startup instead of silently signing with a
        # publicly known constant.
        if self.auth_enabled and not self.app_secret_key.strip():
            raise ValueError(
                "AUTH_ENABLED=true requires APP_SECRET_KEY; refusing to start with a fallback secret "
                "(generate one: python -c \"import secrets;print(secrets.token_hex(32))\")"
            )
        if self.app_env == "production":
            if not self.auth_enabled:
                raise ValueError("APP_ENV=production requires AUTH_ENABLED=true (implicit dev session is not allowed)")
            if len(self.app_secret_key) < 32:
                raise ValueError("APP_ENV=production requires APP_SECRET_KEY of at least 32 characters")
            if not self.session_cookie_secure:
                raise ValueError(
                    "APP_ENV=production requires SESSION_COOKIE_SECURE=true (HTTPS behind a trusted proxy)"
                )
            if not self.database_url:
                raise ValueError("APP_ENV=production requires DATABASE_URL (audit events must be persisted)")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.app_cors_origins.split(",") if origin.strip()]

    @property
    def demo_users_enabled(self) -> bool:
        """Hardcoded demo credentials are limited to development/demo runs.

        The explicit flag can only ever narrow availability in production:
        production always rejects demo credentials regardless of the flag.
        """
        if self.app_env == "production":
            return False
        if self.auth_demo_users_enabled is not None:
            return self.auth_demo_users_enabled
        return self.app_env in {"development", "demo"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
