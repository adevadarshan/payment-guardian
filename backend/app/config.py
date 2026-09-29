# app/config.py — environment-driven settings (Slice 4).
# Rules: no secrets or host/port literals in source; production misconfig
# fails loudly at startup instead of silently running unsafe.

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CORS = "http://localhost:5173,http://localhost:3000"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"
    # Database. Postgres is the deployment target.
    # SQLite is accepted for tests and local runs where Postgres is unavailable.
    # Example Postgres: postgresql+psycopg2://postgres:password@localhost:5432/vhs02
    DATABASE_URL: str = "sqlite:///./vhs02.db"
    CORS_ORIGINS: str = DEFAULT_CORS
    TRUSTED_HOSTS: str = "localhost,127.0.0.1,testserver"
    MODEL_BACKEND: str = "none"  # Slice 4: "none" default; "synthetic-v1" opt-in.
    THRESHOLD_MEDIUM: int = 35
    THRESHOLD_HIGH: int = 75
    PIPELINE_VERSION: str = "slice-4"
    # Test-only escape hatch: when true, POST /api/analyze may use the request's
    # advisory timestamp for the hour-of-day signal (deterministic golden tests).
    # Production MUST keep this false: client time must not move the verdict.
    ALLOW_CLIENT_HOUR: bool = False
    # QR intake limits (Slice 3). Full payloads are retained in result_json
    # only when STORE_QR_PAYLOADS is true; application logs never carry payloads.
    QR_MAX_MB: int = 5
    QR_MAX_MEGAPIXELS: int = 12
    STORE_QR_PAYLOADS: bool = True
    # Slice 4 flags.
    AUTH_REQUIRED: bool = True
    DEMO_EMAIL: str = "demo@vhs02.local"
    DEMO_PASSWORD: str = "demo1234"
    ADVISORY_ENABLED: bool = False
    ADVISORY_PROVIDER: str = "stub"  # stub | http
    ADVISORY_ENDPOINT: str | None = None
    ADVISORY_API_KEY: str | None = None
    ADVISORY_TIMEOUT_S: int = 8
    ADVISORY_MAX_CHARS: int = 600
    RATE_LIMIT_ANALYZE_IP: int = 10
    RATE_LIMIT_ANALYZE_USER: int = 60
    RATE_LIMIT_LOGIN_IP: int = 5
    MAX_CONTENT_BYTES: int = 8 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.TRUSTED_HOSTS.split(",") if h.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


def validate_production(cfg: Settings) -> list[str]:
    """Return human-readable config errors. Empty means production-safe.

    AUTH_REQUIRED=false is permitted ONLY outside production: a production
    server with authentication disabled refuses to start.
    """
    errors: list[str] = []
    if not cfg.is_production:
        return errors
    if cfg.DATABASE_URL.startswith("sqlite"):
        errors.append("production DATABASE_URL must not be SQLite")
    if cfg.CORS_ORIGINS.strip() == DEFAULT_CORS:
        errors.append("production CORS_ORIGINS must be set explicitly")
    if not cfg.AUTH_REQUIRED:
        errors.append("production AUTH_REQUIRED=false is forbidden")
    if cfg.ALLOW_CLIENT_HOUR:
        errors.append("production ALLOW_CLIENT_HOUR must be false")
    return errors


settings = Settings()

