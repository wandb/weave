from __future__ import annotations

import re
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, cast

import clickhouse_connect

from weave.trace_server.intent_vectors import config, metrics
from weave.trace_server.intent_vectors.models import (
    ClusterJob,
    ClusterResult,
    IntentFilters,
    IntentInput,
    IntentRecord,
)

if TYPE_CHECKING:
    from clickhouse_connect.driver.client import Client

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_INTENT_COLUMNS = (
    "intent_id, version, signature, normalized_signature, request_type, status, "
    "source, source_id, role, event_time, attributes, embedding_model, "
    "embedding_dimensions, created_by_user_id, created_at"
)
_INTENT_COLUMNS_WITH_STATE = f"{_INTENT_COLUMNS}, deleted, vector"
_REQUIRED_TABLES = {
    "intent_vectors",
    "cluster_jobs",
    "cluster_results",
}


@dataclass(frozen=True)
class SearchCandidate:
    record: IntentRecord
    vector: list[float]
    deleted: bool


@dataclass(frozen=True)
class ClusterInput:
    intent_id: str
    version: int
    vector: list[float]


class IntentRepository(ABC):
    @abstractmethod
    def startup(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def ready(self) -> bool: ...

    @abstractmethod
    def upsert(
        self,
        project_id: str,
        user_id: str,
        intents: list[IntentInput],
        vectors: dict[str, list[float]],
    ) -> None: ...

    @abstractmethod
    def get(self, project_id: str, intent_id: str) -> IntentRecord | None: ...

    @abstractmethod
    def query(
        self, project_id: str, filters: IntentFilters, limit: int
    ) -> list[IntentRecord]: ...

    @abstractmethod
    def delete(self, project_id: str, intent_id: str, user_id: str) -> bool: ...

    @abstractmethod
    def search_candidates(
        self,
        project_id: str,
        vector: list[float],
        filters: IntentFilters,
        limit: int,
    ) -> list[SearchCandidate]: ...

    @abstractmethod
    def create_cluster_job(
        self, project_id: str, job_id: str, user_id: str, min_cluster_size: int
    ) -> ClusterJob: ...

    @abstractmethod
    def has_active_cluster_job(self) -> bool: ...

    @abstractmethod
    def update_cluster_job(
        self,
        project_id: str,
        job_id: str,
        status: str,
        *,
        vector_count: int | None = None,
        error_code: str | None = None,
    ) -> None: ...

    @abstractmethod
    def get_cluster_job(self, project_id: str, job_id: str) -> ClusterJob | None: ...

    @abstractmethod
    def load_cluster_inputs(self, project_id: str) -> list[ClusterInput]: ...

    @abstractmethod
    def insert_cluster_results(
        self, project_id: str, job_id: str, results: list[ClusterResult]
    ) -> None: ...

    @abstractmethod
    def get_cluster_results(
        self, project_id: str, job_id: str
    ) -> list[ClusterResult]: ...

    @abstractmethod
    def fail_interrupted_cluster_jobs(self) -> None: ...

    @abstractmethod
    def optimize_intents(self) -> None: ...


class ClickHouseIntentRepository(IntentRepository):
    def __init__(self, settings: config.Settings) -> None:
        for label, identifier in (
            ("database", settings.clickhouse_database),
            ("management database", settings.clickhouse_management_database),
        ):
            if _IDENTIFIER.fullmatch(identifier) is None:
                raise ValueError(f"ClickHouse {label} must be a simple identifier")
        self._settings = settings
        self._client: Client | None = None
        self._version_lock = threading.Lock()
        self._last_version = 0

    def startup(self) -> None:
        bootstrap = clickhouse_connect.get_client(
            host=self._settings.clickhouse_host,
            port=self._settings.clickhouse_port,
            username=self._settings.clickhouse_username,
            password=self._settings.clickhouse_password,
            secure=self._settings.clickhouse_secure,
            autogenerate_session_id=False,
        )
        try:
            version = str(bootstrap.command("SELECT version()"))
            self._require_supported_version(version)
        finally:
            bootstrap.close()
        self._client = clickhouse_connect.get_client(
            host=self._settings.clickhouse_host,
            port=self._settings.clickhouse_port,
            username=self._settings.clickhouse_username,
            password=self._settings.clickhouse_password,
            database=self._settings.clickhouse_database,
            secure=self._settings.clickhouse_secure,
            autogenerate_session_id=False,
        )
        self.fail_interrupted_cluster_jobs()

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def ready(self) -> bool:
        try:
            version = str(self._require_client().command("SELECT version()"))
            self._require_supported_version(version)
            migration_rows = (
                self._require_client()
                .query(
                    f"""
                SELECT curr_version, partially_applied_version
                FROM {self._settings.clickhouse_management_database}.migrations
                WHERE db_name = %(database)s
                """,
                    parameters={"database": self._settings.clickhouse_database},
                )
                .result_rows
            )
            table_names = {
                str(row[0])
                for row in self._require_client()
                .query(
                    "SELECT name FROM system.tables WHERE database = currentDatabase()"
                )
                .result_rows
            }
            is_ready = (
                len(migration_rows) == 1
                and _as_int(migration_rows[0][0]) == config.latest_schema_version()
                and migration_rows[0][1] is None
                and _REQUIRED_TABLES <= table_names
            )
        except Exception:
            return False
        else:
            return is_ready

    def upsert(
        self,
        project_id: str,
        user_id: str,
        intents: list[IntentInput],
        vectors: dict[str, list[float]],
    ) -> None:
        now = datetime.now(timezone.utc)
        rows: list[list[object]] = []
        for intent in intents:
            normalized = " ".join(intent.signature.lower().split())
            rows.append(
                [
                    project_id,
                    intent.intent_id,
                    self._next_version(),
                    False,
                    intent.signature,
                    normalized,
                    intent.request_type,
                    intent.status,
                    intent.source,
                    intent.source_id,
                    intent.role,
                    intent.event_time,
                    intent.attributes,
                    config.EMBEDDING_MODEL,
                    config.EMBEDDING_DIMENSIONS,
                    vectors[normalized],
                    user_id,
                    now,
                ]
            )
        columns = [
            "project_id",
            "intent_id",
            "version",
            "deleted",
            "signature",
            "normalized_signature",
            "request_type",
            "status",
            "source",
            "source_id",
            "role",
            "event_time",
            "attributes",
            "embedding_model",
            "embedding_dimensions",
            "vector",
            "created_by_user_id",
            "created_at",
        ]
        with metrics.timed("clickhouse_operation", operation="upsert"):
            self._require_client().insert("intent_vectors", rows, column_names=columns)

    def get(self, project_id: str, intent_id: str) -> IntentRecord | None:
        sql = f"""
            SELECT {_INTENT_COLUMNS_WITH_STATE}
            FROM intent_vectors FINAL
            WHERE project_id = %(project_id)s AND intent_id = %(intent_id)s
            LIMIT 1
        """
        with metrics.timed("clickhouse_operation", operation="get"):
            rows = self._named_query(
                sql, {"project_id": project_id, "intent_id": intent_id}
            )
        if not rows or bool(rows[0]["deleted"]):
            return None
        return self._record(rows[0])

    def query(
        self, project_id: str, filters: IntentFilters, limit: int
    ) -> list[IntentRecord]:
        where, parameters = self._filter_sql(project_id, filters)
        parameters["limit"] = limit
        sql = f"""
            SELECT {_INTENT_COLUMNS}
            FROM intent_vectors FINAL
            WHERE {where} AND deleted = 0
            ORDER BY event_time DESC, intent_id
            LIMIT %(limit)s
        """
        with metrics.timed("clickhouse_operation", operation="query"):
            rows = self._named_query(sql, parameters)
        return [self._record(row) for row in rows]

    def delete(self, project_id: str, intent_id: str, user_id: str) -> bool:
        sql = f"""
            SELECT {_INTENT_COLUMNS_WITH_STATE}
            FROM intent_vectors FINAL
            WHERE project_id = %(project_id)s AND intent_id = %(intent_id)s
            LIMIT 1
        """
        rows = self._named_query(
            sql, {"project_id": project_id, "intent_id": intent_id}
        )
        if not rows or bool(rows[0]["deleted"]):
            return False
        row = rows[0]
        self._require_client().insert(
            "intent_vectors",
            [
                [
                    project_id,
                    intent_id,
                    self._next_version(),
                    True,
                    row["signature"],
                    row["normalized_signature"],
                    row["request_type"],
                    row["status"],
                    row["source"],
                    row["source_id"],
                    row["role"],
                    row["event_time"],
                    row["attributes"],
                    row["embedding_model"],
                    row["embedding_dimensions"],
                    row["vector"],
                    user_id,
                    datetime.now(timezone.utc),
                ]
            ],
            column_names=[
                "project_id",
                "intent_id",
                "version",
                "deleted",
                "signature",
                "normalized_signature",
                "request_type",
                "status",
                "source",
                "source_id",
                "role",
                "event_time",
                "attributes",
                "embedding_model",
                "embedding_dimensions",
                "vector",
                "created_by_user_id",
                "created_at",
            ],
        )
        metrics.emit("clickhouse_operation", operation="delete", outcome="success")
        return True

    def search_candidates(
        self,
        project_id: str,
        vector: list[float],
        filters: IntentFilters,
        limit: int,
    ) -> list[SearchCandidate]:
        where, parameters = self._filter_sql(project_id, filters)
        parameters.update({"vector": vector, "limit": limit})
        sql = f"""
            SELECT {_INTENT_COLUMNS_WITH_STATE}, cosineDistance(vector, %(vector)s) AS distance
            FROM intent_vectors
            WHERE {where} AND deleted = 0
            ORDER BY distance
            LIMIT %(limit)s
        """
        with metrics.timed("clickhouse_operation", operation="search"):
            rows = self._named_query(sql, parameters)
        return [
            SearchCandidate(
                record=self._record(row),
                vector=_as_vector(row["vector"]),
                deleted=bool(row["deleted"]),
            )
            for row in rows
        ]

    def create_cluster_job(
        self, project_id: str, job_id: str, user_id: str, min_cluster_size: int
    ) -> ClusterJob:
        now = datetime.now(timezone.utc)
        self._insert_job_row(
            project_id=project_id,
            job_id=job_id,
            status="queued",
            min_cluster_size=min_cluster_size,
            vector_count=None,
            error_code=None,
            user_id=user_id,
            created_at=now,
            started_at=None,
            completed_at=None,
        )
        return ClusterJob(
            job_id=job_id,
            status="queued",
            min_cluster_size=min_cluster_size,
            created_by_user_id=user_id,
            created_at=now,
        )

    def has_active_cluster_job(self) -> bool:
        count = _as_int(
            self._require_client().command(
                "SELECT count() FROM cluster_jobs FINAL WHERE status IN ('queued', 'running')"
            )
        )
        return count > 0

    def update_cluster_job(
        self,
        project_id: str,
        job_id: str,
        status: str,
        *,
        vector_count: int | None = None,
        error_code: str | None = None,
    ) -> None:
        current = self.get_cluster_job(project_id, job_id)
        if current is None:
            raise LookupError("cluster job not found")
        now = datetime.now(timezone.utc)
        started_at = current.started_at
        completed_at = current.completed_at
        if status == "running":
            started_at = now
        elif status in {"completed", "failed"}:
            completed_at = now
        self._insert_job_row(
            project_id=project_id,
            job_id=job_id,
            status=status,
            min_cluster_size=current.min_cluster_size,
            vector_count=vector_count
            if vector_count is not None
            else current.vector_count,
            error_code=error_code,
            user_id=current.created_by_user_id,
            created_at=current.created_at,
            started_at=started_at,
            completed_at=completed_at,
        )

    def get_cluster_job(self, project_id: str, job_id: str) -> ClusterJob | None:
        rows = self._named_query(
            """
            SELECT job_id, status, min_cluster_size, vector_count, error_code,
                   created_by_user_id, created_at, started_at, completed_at
            FROM cluster_jobs FINAL
            WHERE project_id = %(project_id)s AND job_id = %(job_id)s
            LIMIT 1
            """,
            {"project_id": project_id, "job_id": job_id},
        )
        if not rows:
            return None
        row = rows[0]
        return ClusterJob(
            job_id=str(row["job_id"]),
            status=_as_job_status(row["status"]),
            min_cluster_size=_as_int(row["min_cluster_size"]),
            vector_count=_as_int(row["vector_count"])
            if row["vector_count"] is not None
            else None,
            error_code=str(row["error_code"]) if row["error_code"] else None,
            created_by_user_id=str(row["created_by_user_id"]),
            created_at=_as_datetime(row["created_at"]),
            started_at=_as_optional_datetime(row["started_at"]),
            completed_at=_as_optional_datetime(row["completed_at"]),
        )

    def load_cluster_inputs(self, project_id: str) -> list[ClusterInput]:
        rows = self._named_query(
            """
            SELECT intent_id, version, vector
            FROM intent_vectors FINAL
            WHERE project_id = %(project_id)s AND deleted = 0
            ORDER BY intent_id
            LIMIT %(limit)s
            """,
            {"project_id": project_id, "limit": config.MAX_CLUSTER_VECTORS + 1},
        )
        return [
            ClusterInput(
                intent_id=str(row["intent_id"]),
                version=_as_int(row["version"]),
                vector=_as_vector(row["vector"]),
            )
            for row in rows
        ]

    def insert_cluster_results(
        self, project_id: str, job_id: str, results: list[ClusterResult]
    ) -> None:
        if not results:
            return
        self._require_client().insert(
            "cluster_results",
            [
                [
                    project_id,
                    job_id,
                    item.intent_id,
                    item.input_version,
                    item.cluster_id,
                    item.probability,
                ]
                for item in results
            ],
            column_names=[
                "project_id",
                "job_id",
                "intent_id",
                "input_version",
                "cluster_id",
                "probability",
            ],
        )

    def get_cluster_results(self, project_id: str, job_id: str) -> list[ClusterResult]:
        rows = self._named_query(
            """
            SELECT intent_id, input_version, cluster_id, probability
            FROM cluster_results
            WHERE project_id = %(project_id)s AND job_id = %(job_id)s
            ORDER BY intent_id
            """,
            {"project_id": project_id, "job_id": job_id},
        )
        return [
            ClusterResult(
                intent_id=str(row["intent_id"]),
                input_version=_as_int(row["input_version"]),
                cluster_id=_as_int(row["cluster_id"]),
                probability=_as_float(row["probability"]),
            )
            for row in rows
        ]

    def fail_interrupted_cluster_jobs(self) -> None:
        rows = self._named_query(
            """
            SELECT project_id, job_id
            FROM cluster_jobs FINAL
            WHERE status IN ('queued', 'running')
            """
        )
        for row in rows:
            self.update_cluster_job(
                str(row["project_id"]),
                str(row["job_id"]),
                "failed",
                error_code="service_restarted",
            )

    def optimize_intents(self) -> None:
        with metrics.timed("clickhouse_operation", operation="optimize"):
            self._require_client().command("OPTIMIZE TABLE intent_vectors FINAL")

    def _insert_job_row(
        self,
        *,
        project_id: str,
        job_id: str,
        status: str,
        min_cluster_size: int,
        vector_count: int | None,
        error_code: str | None,
        user_id: str,
        created_at: datetime,
        started_at: datetime | None,
        completed_at: datetime | None,
    ) -> None:
        self._require_client().insert(
            "cluster_jobs",
            [
                [
                    project_id,
                    job_id,
                    self._next_version(),
                    status,
                    min_cluster_size,
                    vector_count,
                    error_code,
                    user_id,
                    created_at,
                    started_at,
                    completed_at,
                ]
            ],
            column_names=[
                "project_id",
                "job_id",
                "version",
                "status",
                "min_cluster_size",
                "vector_count",
                "error_code",
                "created_by_user_id",
                "created_at",
                "started_at",
                "completed_at",
            ],
        )

    def _next_version(self) -> int:
        with self._version_lock:
            self._last_version = max(time.time_ns(), self._last_version + 1)
            return self._last_version

    def _named_query(
        self, sql: str, parameters: dict[str, object] | None = None
    ) -> list[dict[str, object]]:
        result = self._require_client().query(sql, parameters=parameters)
        return [
            dict(zip(result.column_names, row, strict=True))
            for row in result.result_rows
        ]

    @staticmethod
    def _record(row: dict[str, object]) -> IntentRecord:
        attributes = _as_attributes(row["attributes"])
        return IntentRecord(
            intent_id=str(row["intent_id"]),
            version=_as_int(row["version"]),
            signature=str(row["signature"]),
            normalized_signature=str(row["normalized_signature"]),
            request_type=str(row["request_type"]),
            status=str(row["status"]),
            source=str(row["source"]),
            source_id=str(row["source_id"]),
            role=str(row["role"]),
            event_time=_as_datetime(row["event_time"]),
            attributes=attributes,
            embedding_model=str(row["embedding_model"]),
            embedding_dimensions=_as_int(row["embedding_dimensions"]),
            created_by_user_id=str(row["created_by_user_id"]),
            created_at=_as_datetime(row["created_at"]),
        )

    @staticmethod
    def _filter_sql(
        project_id: str, filters: IntentFilters
    ) -> tuple[str, dict[str, object]]:
        clauses = ["project_id = %(project_id)s"]
        parameters: dict[str, object] = {"project_id": project_id}
        for field in ("intent_id", "request_type", "status", "source"):
            value = getattr(filters, field)
            if value is not None:
                clauses.append(f"{field} = %({field})s")
                parameters[field] = value
        if filters.event_time_from is not None:
            clauses.append("event_time >= %(event_time_from)s")
            parameters["event_time_from"] = filters.event_time_from
        if filters.event_time_to is not None:
            clauses.append("event_time <= %(event_time_to)s")
            parameters["event_time_to"] = filters.event_time_to
        return " AND ".join(clauses), parameters

    def _require_client(self) -> Client:
        if self._client is None:
            raise RuntimeError("repository has not started")
        return self._client

    @staticmethod
    def _require_supported_version(version: str) -> None:
        try:
            major = int(version.split(".", 1)[0])
        except ValueError as exc:
            raise RuntimeError(f"invalid ClickHouse version: {version}") from exc
        if major != config.SUPPORTED_CLICKHOUSE_MAJOR:
            raise RuntimeError(
                f"unsupported ClickHouse version {version}; expected {config.SUPPORTED_CLICKHOUSE_MAJOR}.x"
            )


def _as_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected integer database value, got {type(value).__name__}")


def _as_float(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError(f"expected float database value, got {type(value).__name__}")


def _as_vector(value: object) -> list[float]:
    if not isinstance(value, list | tuple):
        raise TypeError(f"expected vector database value, got {type(value).__name__}")
    return [_as_float(item) for item in value]


def _as_attributes(value: object) -> dict[str, str]:
    if isinstance(value, dict):
        return {str(key): str(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        attributes: dict[str, str] = {}
        for entry in value:
            if not isinstance(entry, list | tuple) or len(entry) != 2:
                raise TypeError("expected key/value pairs in map database value")
            attributes[str(entry[0])] = str(entry[1])
        return attributes
    raise TypeError(f"expected map database value, got {type(value).__name__}")


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    raise TypeError(f"expected datetime database value, got {type(value).__name__}")


def _as_optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    return _as_datetime(value)


def _as_job_status(
    value: object,
) -> Literal["queued", "running", "completed", "failed"]:
    if value not in {"queued", "running", "completed", "failed"}:
        raise ValueError(f"unknown cluster job status: {value}")
    return cast("Literal['queued', 'running', 'completed', 'failed']", value)
