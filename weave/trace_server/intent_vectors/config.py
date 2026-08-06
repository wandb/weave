"""Configuration for the intent vector store."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path

EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 1024
EMBEDDING_BATCH_SIZE = 256
EMBEDDING_CACHE_SIZE = 10_000
MAX_BATCH_SIZE = 256
MAX_SIGNATURE_CHARS = 8_192
MAX_REQUEST_BODY_BYTES = 2 * 1024 * 1024
MAX_LIST_RESULTS = 500
MAX_SEARCH_K = 100
MAX_SEARCH_CANDIDATES = 500
SEARCH_OVERFETCH_MULTIPLIER = 5
MAX_CLUSTER_VECTORS = 100_000
MIN_CLUSTER_SIZE_DEFAULT = 3
MIN_CLUSTER_SIZE_MIN = 2
MIN_CLUSTER_SIZE_MAX = 100
SUPPORTED_CLICKHOUSE_MAJOR = 26
STARTUP_RETRY_ATTEMPTS = 30
STARTUP_RETRY_DELAY_SECONDS = 1.0

CLICKHOUSE_HOST_ENV = "WF_CLICKHOUSE_HOST"
CLICKHOUSE_PORT_ENV = "WF_CLICKHOUSE_PORT"
CLICKHOUSE_USERNAME_ENV = "WF_CLICKHOUSE_USER"
CLICKHOUSE_PASSWORD_ENV = "WF_CLICKHOUSE_PASS"
CLICKHOUSE_DATABASE_ENV = "INTENT_VECTOR_CLICKHOUSE_DATABASE"
CLICKHOUSE_MANAGEMENT_DATABASE_ENV = "WF_CLICKHOUSE_MANAGEMENT_DATABASE"
CLICKHOUSE_SECURE_ENV = "WF_CLICKHOUSE_SECURE"


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    clickhouse_host: str
    clickhouse_port: int
    clickhouse_username: str
    clickhouse_password: str
    clickhouse_database: str
    clickhouse_management_database: str
    clickhouse_secure: bool

    @classmethod
    def from_env(cls) -> Settings:
        port = int(os.environ.get(CLICKHOUSE_PORT_ENV, "8123"))
        return cls(
            clickhouse_host=os.environ.get(CLICKHOUSE_HOST_ENV, "localhost"),
            clickhouse_port=port,
            clickhouse_username=os.environ.get(CLICKHOUSE_USERNAME_ENV, "default"),
            clickhouse_password=os.environ.get(CLICKHOUSE_PASSWORD_ENV, ""),
            clickhouse_database=os.environ.get(
                CLICKHOUSE_DATABASE_ENV, "intent_vectors"
            ),
            clickhouse_management_database=os.environ.get(
                CLICKHOUSE_MANAGEMENT_DATABASE_ENV, "db_management"
            ),
            clickhouse_secure=_bool_env(CLICKHOUSE_SECURE_ENV, port == 8443),
        )


def migrations_dir() -> Path:
    return Path(__file__).with_name("migrations")


@cache
def latest_schema_version() -> int:
    versions = sorted(
        int(path.name.split("_", 1)[0]) for path in migrations_dir().glob("*.up.sql")
    )
    if not versions:
        raise RuntimeError("no intent vector migrations found")
    if versions != list(range(1, len(versions) + 1)):
        raise RuntimeError("intent vector migrations must be contiguous from version 1")
    return versions[-1]
