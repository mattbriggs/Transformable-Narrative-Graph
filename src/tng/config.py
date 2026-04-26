"""Application configuration loaded from environment variables.

Uses ``pydantic-settings`` so every setting is type-validated and
documented.  Secrets (Neo4j credentials) are read from a Docker-secret
file when ``NEO4J_AUTH_FILE`` is set, falling back to direct env-var
overrides for local development outside of Docker.

The module exposes a single ``get_settings()`` function that returns a
cached ``Settings`` instance (singleton via ``lru_cache``).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Runtime configuration for the TNGS application.

    :param neo4j_uri: Bolt URI for the Neo4j instance.
    :param neo4j_database: Name of the target Neo4j database.
    :param neo4j_user: Neo4j username.
    :param neo4j_password: Neo4j password (resolved from secret file when
        ``NEO4J_AUTH_FILE`` is present).
    :param neo4j_auth_file: Path to a ``username/password`` secret file
        injected by Docker secrets.  When set, overrides ``neo4j_user`` and
        ``neo4j_password``.
    :param api_secret_key: HMAC key used for Bearer token signing.
    :param confidence_threshold: Atoms/events below this score are flagged
        for human review rather than silently discarded.
    :param log_level: Python logging level string (DEBUG, INFO, WARNING…).
    """

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_database: str = Field(default="neo4j")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="neo4j")
    neo4j_auth_file: str | None = Field(default=None)

    api_secret_key: str = Field(default="dev-secret-change-me")
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    log_level: str = Field(default="INFO")

    @model_validator(mode="after")
    def _resolve_secret_file(self) -> "Settings":
        """Read Neo4j credentials from a Docker-secret file if one is configured."""
        path_str = self.neo4j_auth_file or os.environ.get("NEO4J_AUTH_FILE")
        if path_str:
            path = Path(path_str)
            if path.is_file():
                content = path.read_text().strip()
                if "/" in content:
                    self.neo4j_user, self.neo4j_password = content.split("/", 1)
                    logger.debug("Neo4j credentials loaded from secret file.")
                else:
                    logger.warning(
                        "NEO4J_AUTH_FILE content does not contain '/'; ignoring."
                    )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    :returns: Validated ``Settings`` instance.
    """
    settings = Settings()
    logging.basicConfig(level=settings.log_level.upper())
    return settings
