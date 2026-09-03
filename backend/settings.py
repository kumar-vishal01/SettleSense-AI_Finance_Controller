"""Service-level settings from environment variables.

Scope: non-secret configuration only (AGENTS.md section 3). Secrets such as
AI provider keys live in the process environment at runtime and are never
read into modules that log, persist, or serialize settings.

Domain tuning (thresholds, windows) is separate: see backend/config.py.
Domain code must not import this module; only the service layer does.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_env_file(path: str | Path = ".env") -> None:
    """Minimal .env loader: KEY=VALUE lines; existing environment wins.
    Values never leave the process. Called once at import; .env is
    git-ignored, and real secrets belong only there."""
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file()


def _split_origins(raw: str) -> list[str]:
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


@dataclass(frozen=True)
class ServiceSettings:
    """Everything the FastAPI layer needs from the environment."""

    environment: str = "local"          # local | docker | production
    timezone: str = "Asia/Kolkata"      # display timezone; internals stay UTC
    database_path: Path = Path("settlesense.db")
    cors_origins: list[str] = field(default_factory=lambda: [
        "http://localhost:5173",        # vite dev server
        "http://localhost:4173",        # vite preview
    ])
    log_level: str = "info"


def service_settings() -> ServiceSettings:
    """Build settings from the process environment (pure; no I/O)."""
    env = os.environ
    return ServiceSettings(
        environment=env.get("SETTLESENSE_ENV", "local"),
        timezone=env.get("SETTLESENSE_TIMEZONE", "Asia/Kolkata"),
        database_path=Path(env.get("SETTLESENSE_DB_PATH", "settlesense.db")),
        cors_origins=_split_origins(
            env.get(
                "SETTLESENSE_CORS_ORIGINS",
                "http://localhost:5173,http://localhost:4173",
            )
        ),
        log_level=env.get("SETTLESENSE_LOG_LEVEL", "info").lower(),
    )
