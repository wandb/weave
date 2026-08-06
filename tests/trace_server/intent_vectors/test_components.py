from __future__ import annotations

import math
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from weave.trace_server.intent_vectors import config
from weave.trace_server.intent_vectors.embeddings import (
    OpenAIEmbeddingProvider,
    l2_normalize,
    normalize_text,
)
from weave.trace_server.intent_vectors.models import IntentFilters
from weave.trace_server.intent_vectors.repository import ClickHouseIntentRepository


class _EmbeddingsAPI:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        inputs = kwargs["input"]
        assert isinstance(inputs, list)
        return SimpleNamespace(
            data=[
                SimpleNamespace(index=index, embedding=[3.0, 4.0] + [0.0] * 1022)
                for index, _ in enumerate(inputs)
            ]
        )


class _OpenAI:
    def __init__(self) -> None:
        self.embeddings = _EmbeddingsAPI()


class _QueryResult:
    def __init__(
        self,
        *,
        column_names: list[str] | None = None,
        result_rows: list[tuple[object, ...]] | None = None,
    ) -> None:
        self.column_names = column_names or []
        self.result_rows = result_rows or []


class _RecordingClient:
    def __init__(self) -> None:
        self.queries: list[tuple[str, dict[str, object] | None]] = []

    def command(self, sql: str) -> str:
        assert sql == "SELECT version()"
        return "26.4.4"

    def query(
        self, sql: str, parameters: dict[str, object] | None = None
    ) -> _QueryResult:
        self.queries.append((sql, parameters))
        if "FROM db_management.migrations" in sql:
            return _QueryResult(result_rows=[(3, None)])
        if "FROM system.tables" in sql:
            return _QueryResult(
                result_rows=[
                    ("intent_vectors",),
                    ("cluster_jobs",),
                    ("cluster_results",),
                ]
            )
        return _QueryResult()


def _settings() -> config.Settings:
    return config.Settings(
        clickhouse_host="localhost",
        clickhouse_port=8123,
        clickhouse_username="default",
        clickhouse_password="",
        clickhouse_database="intent_vectors",
        clickhouse_management_database="db_management",
        clickhouse_secure=False,
    )


def _unit_vector(index: int) -> list[float]:
    vector = [0.0] * config.EMBEDDING_DIMENSIONS
    vector[index] = 1.0
    return vector


def test_embedding_models_repository_queries_and_schema_contract() -> None:
    # Normalization, batching, caching, and L2 output.
    assert normalize_text("  Add   DARK\nMode ") == "add dark mode"
    with pytest.raises(ValueError, match="empty"):
        normalize_text(" \n ")
    with pytest.raises(ValueError, match="dimensions"):
        l2_normalize([1.0])

    openai = _OpenAI()
    embedder = OpenAIEmbeddingProvider(openai)  # type: ignore[arg-type]
    vectors = embedder.embed([" Hello  World ", "hello world"])
    assert len(openai.embeddings.calls) == 1
    assert math.isclose(sum(value * value for value in vectors["hello world"]), 1.0)
    assert embedder.embed(["HELLO WORLD"])["hello world"] == vectors["hello world"]
    assert len(openai.embeddings.calls) == 1

    with pytest.raises(ValueError, match="event_time_from"):
        IntentFilters(
            event_time_from=datetime(2026, 2, 1, tzinfo=UTC),
            event_time_to=datetime(2026, 1, 1, tzinfo=UTC),
        )

    # Point/list reads are authoritative; ANN reads deliberately omit FINAL.
    repository = ClickHouseIntentRepository(_settings())
    client = _RecordingClient()
    repository._client = client  # type: ignore[assignment]
    assert repository.ready()
    assert repository.get("trusted-project", "intent") is None
    repository.query("trusted-project", IntentFilters(status="ok"), 50)
    repository.search_candidates(
        "trusted-project", _unit_vector(0), IntentFilters(source="weave"), 25
    )
    point_sql = client.queries[-3][0]
    list_sql = client.queries[-2][0]
    search_sql = client.queries[-1][0]
    assert "FINAL" in point_sql
    assert "FINAL" in list_sql
    assert "FINAL" not in search_sql
    assert "cosineDistance" in search_sql
    assert "ORDER BY distance" in search_sql
    with pytest.raises(RuntimeError, match="unsupported"):
        repository._require_supported_version("25.8.1")

    migration_text = "\n".join(
        path.read_text() for path in sorted(config.migrations_dir().glob("*.up.sql"))
    ).lower()
    assert config.latest_schema_version() == 3
    assert "replacingmergetree(version)" in migration_text
    assert "cityhash64(project_id) % 32" in migration_text
    assert "vector_similarity('hnsw', 'cosinedistance', 1024, 'bf16'" in migration_text
    assert "drop table" not in migration_text
    assert "truncate table" not in migration_text
