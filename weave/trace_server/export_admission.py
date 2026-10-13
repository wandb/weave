"""Deployment-wide export admission with request-time orphan reconciliation."""

import json
import logging
from dataclasses import dataclass, field
from threading import Event, Thread

import redis
from clickhouse_connect.driver.client import Client as CHClient

from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server.redis_client import get_redis_client

logger = logging.getLogger(__name__)

LEASE_KEY = "weave:export:lease"
ACTIVE_KEY = "weave:export:active"
LEASE_SECONDS = 60
RENEW_SECONDS = 15
QUERY_PREFIX = "weave-export:"

_UPDATE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
local current = redis.call('GET', KEYS[2]) or ''
if current ~= ARGV[2] then return 0 end
redis.call('SET', KEYS[2], ARGV[3])
return 1
"""
_RENEW = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
return redis.call('EXPIRE', KEYS[1], ARGV[2])
"""
_RELEASE = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
if ARGV[2] == 'clear' and redis.call('GET', KEYS[2]) == ARGV[3] then
    redis.call('DEL', KEYS[2])
end
redis.call('DEL', KEYS[1])
return 1
"""


class AdmissionError(Exception):
    def __init__(self, http_status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.code = code


def export_query_id(job_id: str, target: str) -> str:
    return f"{QUERY_PREFIX}{job_id}:{target}"


def _system_table(table: str, cluster: str | None) -> str:
    if cluster is None:
        return f"system.{table}"
    return f"clusterAllReplicas({{cluster:String}}, system.{table})"


def has_running_exports(client: CHClient, cluster: str | None) -> bool:
    """Discover marked and legacy export queries; unreachable replicas are errors."""
    sql = (
        f"SELECT count() FROM {_system_table('processes', cluster)} "
        "WHERE startsWith(query_id, {prefix:String}) "
        "OR startsWith(initial_query_id, {prefix:String}) "
        "OR startsWith(query, {legacy_insert:String})"
    )
    return bool(
        client.query(
            sql,
            parameters={
                "cluster": cluster,
                "prefix": QUERY_PREFIX,
                "legacy_insert": "INSERT INTO FUNCTION s3(weave_exports,",
            },
            settings=ch_settings.merge_default_query_settings(
                {"skip_unavailable_shards": 0, "max_execution_time": 10}
            ),
        ).result_rows[0][0]
    )


def _query_ended(client: CHClient, query_id: str, cluster: str | None) -> bool:
    sql = (
        f"SELECT count() FROM {_system_table('query_log', cluster)} "
        "WHERE query_id = {qid:String} AND event_date >= today() - 1 "
        "AND (type = 'QueryFinish' OR startsWith(toString(type), 'Exception'))"
    )
    return bool(
        client.query(
            sql,
            parameters={"cluster": cluster, "qid": query_id},
            settings=ch_settings.merge_default_query_settings(
                {"skip_unavailable_shards": 0, "max_execution_time": 10}
            ),
        ).result_rows[0][0]
    )


@dataclass
class ExportAdmission:
    redis_client: redis.Redis
    job_id: str
    record: str = ""
    _stop: Event = field(default_factory=Event)
    _lost: Event = field(default_factory=Event)
    _heartbeat: Thread | None = None

    def _eval(self, script: str, *args: str | int) -> int:
        try:
            return int(self.redis_client.eval(script, 2, LEASE_KEY, ACTIVE_KEY, *args))
        except redis.RedisError as exc:
            raise AdmissionError(
                503, "EXPORT_ADMISSION_UNAVAILABLE", "export admission unavailable"
            ) from exc

    def _replace_record(self, query_id: str) -> None:
        next_record = json.dumps({"job_id": self.job_id, "query_id": query_id})
        if self._lost.is_set() or not self._eval(
            _UPDATE, self.job_id, self.record, next_record
        ):
            raise AdmissionError(
                409, "EXPORT_LEASE_LOST", "export worker no longer owns admission"
            )
        self.record = next_record

    def prepare_query(self, query_id: str) -> None:
        # Persist intent before submission: an expired lease cannot fence an HTTP send.
        self._replace_record(query_id)

    def reconcile(self, client: CHClient, cluster: str | None) -> None:
        self._heartbeat = Thread(target=self._renew, daemon=True)
        self._heartbeat.start()
        self.record = self.redis_client.get(ACTIVE_KEY) or ""
        if has_running_exports(client, cluster):
            raise AdmissionError(409, "EXPORT_BUSY", "an export is still running")
        if self.record:
            previous = json.loads(self.record)
            query_id = previous["query_id"]
            if not isinstance(query_id, str):
                raise ValueError("invalid active export query id")
            if query_id and not _query_ended(client, query_id, cluster):
                raise AdmissionError(
                    409, "EXPORT_BUSY", "previous export outcome is not confirmed"
                )
        self._replace_record("")

    def _renew(self) -> None:
        while not self._stop.wait(RENEW_SECONDS):
            try:
                if self._eval(_RENEW, self.job_id, LEASE_SECONDS):
                    continue
            except AdmissionError:
                logger.warning("Export admission renewal unavailable")
            self._lost.set()
            return

    def close(self, *, completed: bool) -> None:
        self._stop.set()
        if self._heartbeat is not None:
            self._heartbeat.join()
        self._eval(
            _RELEASE,
            self.job_id,
            "clear" if completed else "keep",
            self.record,
        )


def acquire_export_admission(
    client: CHClient, job_id: str, cluster: str | None
) -> ExportAdmission:
    redis_client = get_redis_client()
    if redis_client is None:
        raise AdmissionError(
            503, "EXPORT_ADMISSION_UNAVAILABLE", "export requires shared Redis"
        )
    admission = ExportAdmission(redis_client, job_id)
    try:
        claimed = redis_client.set(LEASE_KEY, job_id, nx=True, ex=LEASE_SECONDS)
    except redis.RedisError as exc:
        raise AdmissionError(
            503, "EXPORT_ADMISSION_UNAVAILABLE", "export admission unavailable"
        ) from exc
    if not claimed:
        raise AdmissionError(409, "EXPORT_BUSY", "an export is already active")
    try:
        admission.reconcile(client, cluster)
    except Exception as exc:
        try:
            admission.close(completed=False)
        except AdmissionError:
            logger.warning("Export admission cleanup unavailable")
        if isinstance(exc, AdmissionError):
            raise
        raise AdmissionError(
            503, "EXPORT_ADMISSION_UNAVAILABLE", "cannot verify export admission"
        ) from exc
    return admission
