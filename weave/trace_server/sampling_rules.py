from __future__ import annotations

import datetime
import logging
import threading

import ddtrace
import redis
from cachetools import TTLCache
from clickhouse_connect.driver.client import Client as CHClient
from pydantic import ValidationError

from weave.trace.sampling import build_sampling_etag, validate_glob_pattern
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.redis_client import get_redis_client

logger = logging.getLogger(__name__)

SAMPLING_RULE_CACHE_SIZE = 10_000
SAMPLING_RULE_CACHE_TTL_SECS = 300
REDIS_SAMPLING_KEY_PREFIX = "weave:sampling:"
REDIS_SAMPLING_EXPIRY_SECS = 300
MAX_ACTIVE_SAMPLING_RULES_PER_PROJECT = 200

PROJECT_SCOPE_PREFIX = "project:"
MONITOR_SCOPE_PREFIX = "monitor:"

_sampling_snapshot_cache: TTLCache[
    tuple[str, tsi.SamplingConsumer, str | None], tsi.SamplingRulesSnapshotRes
] = TTLCache(maxsize=SAMPLING_RULE_CACHE_SIZE, ttl=SAMPLING_RULE_CACHE_TTL_SECS)
_sampling_cache_generation: dict[str, int] = {}
_sampling_snapshot_cache_lock = threading.Lock()


@ddtrace.tracer.wrap(name="sampling_rules.get_sampling_rules_snapshot")
def get_sampling_rules_snapshot(
    project_id: str,
    consumer: tsi.SamplingConsumer,
    monitor_id: str | None,
    ch_client: CHClient,
) -> tsi.SamplingRulesSnapshotRes:
    cached = _l1_get(project_id, consumer, monitor_id)
    if cached is not None:
        set_current_span_dd_tags({"sampling.cache_hit": "L1"})
        return cached

    redis_client = get_redis_client()
    if redis_client is not None:
        redis_snapshot = _l2_get(redis_client, project_id, consumer, monitor_id)
        if redis_snapshot is not None:
            _l1_set(project_id, consumer, monitor_id, redis_snapshot)
            set_current_span_dd_tags({"sampling.cache_hit": "L2"})
            return redis_snapshot

    generation = _cache_generation(project_id)
    all_rules = query_clickhouse_sampling_rules(ch_client, project_id)
    snapshot = build_sampling_rules_snapshot(project_id, consumer, monitor_id, all_rules)
    set_current_span_dd_tags(
        {"sampling.cache_hit": "clickhouse", "sampling.rule_count": len(snapshot.rules)}
    )

    if _cache_generation(project_id) == generation:
        if redis_client is not None:
            _l2_set(redis_client, snapshot, consumer, monitor_id)
        _l1_set(project_id, consumer, monitor_id, snapshot)
    return snapshot


@ddtrace.tracer.wrap(name="sampling_rules.query_clickhouse")
def query_clickhouse_sampling_rules(
    ch_client: CHClient, project_id: str
) -> list[tsi.SamplingRuleSchema]:
    result = ch_client.query(
        "SELECT "
        "scope, "
        "op_pattern, "
        "argMax(rate, updated_at) AS rate, "
        "argMax(enabled, updated_at) AS is_enabled, "
        "max(updated_at) AS latest_updated_at "
        "FROM sampling_rules "
        "WHERE project_id = {project_id:String} "
        "GROUP BY scope, op_pattern "
        "HAVING is_enabled = 1 "
        "ORDER BY scope, op_pattern",
        parameters={"project_id": project_id},
    )
    rules: list[tsi.SamplingRuleSchema] = []
    for scope, op_pattern, rate, _enabled, updated_at in result.result_rows:
        try:
            normalized_pattern = normalize_op_pattern(op_pattern)
            validate_glob_pattern(normalized_pattern)
        except ValueError:
            logger.exception(
                "Dropping invalid sampling rule from snapshot for project=%s scope=%s op_pattern=%s",
                project_id,
                scope,
                op_pattern,
            )
            continue
        rules.append(
            tsi.SamplingRuleSchema(
                scope=str(scope),
                op_pattern=normalized_pattern,
                rate=float(rate),
                updated_at=_coerce_datetime(updated_at),
            )
        )
    return rules


def build_sampling_rules_snapshot(
    project_id: str,
    consumer: tsi.SamplingConsumer,
    monitor_id: str | None,
    all_rules: list[tsi.SamplingRuleSchema],
) -> tsi.SamplingRulesSnapshotRes:
    filtered_rules = _filter_rules_for_consumer(all_rules, consumer, monitor_id)
    latest_updated_at = max(
        (rule.updated_at for rule in filtered_rules),
        default=datetime.datetime.now(datetime.timezone.utc),
    )
    return tsi.SamplingRulesSnapshotRes(
        project_id=project_id,
        rules=filtered_rules,
        etag=build_sampling_etag(filtered_rules),
        snapshot_updated_at=latest_updated_at,
        ttl_seconds=SAMPLING_RULE_CACHE_TTL_SECS,
    )


def validate_sampling_rule_update(
    req: tsi.SamplingRulesUpdateReq,
    active_rules: list[tsi.SamplingRuleSchema],
) -> str:
    op_pattern = normalize_op_pattern(req.op_pattern)
    if not 0 <= req.rate <= 1:
        raise ValueError("rate must be between 0 and 1")
    if not req.wb_user_id:
        raise ValueError("wb_user_id is required for audit trail")
    validate_scope(req.project_id, req.scope)
    validate_glob_pattern(op_pattern)
    if req.enabled and req.rate >= 1.0 and op_pattern == "":
        raise ValueError('rate=1.0 with an empty op_pattern is a no-op')

    projected = {(rule.scope, rule.op_pattern): rule for rule in active_rules}
    key = (req.scope, op_pattern)
    if req.enabled:
        projected[key] = tsi.SamplingRuleSchema(
            scope=req.scope,
            op_pattern=op_pattern,
            rate=req.rate,
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
    else:
        projected.pop(key, None)
    if len(projected) > MAX_ACTIVE_SAMPLING_RULES_PER_PROJECT:
        raise ValueError(
            f"active sampling rules per project cannot exceed {MAX_ACTIVE_SAMPLING_RULES_PER_PROJECT}"
        )
    return op_pattern


def normalize_op_pattern(op_pattern: str | None) -> str:
    return op_pattern or ""


def validate_scope(project_id: str, scope: str) -> None:
    if scope == f"{PROJECT_SCOPE_PREFIX}{project_id}":
        return
    if scope.startswith(MONITOR_SCOPE_PREFIX) and len(scope) > len(MONITOR_SCOPE_PREFIX):
        return
    if scope.startswith("org:"):
        return
    raise ValueError(
        "scope must be project:<project_id>, monitor:<monitor_id>, or reserved org:<org_id>"
    )


def invalidate_sampling_rules_cache(project_id: str) -> None:
    with _sampling_snapshot_cache_lock:
        _sampling_cache_generation[project_id] = (
            _sampling_cache_generation.get(project_id, 0) + 1
        )
        for key in list(_sampling_snapshot_cache.keys()):
            if key[0] == project_id:
                _sampling_snapshot_cache.pop(key, None)

    redis_client = get_redis_client()
    if redis_client is not None:
        _l2_delete_project(redis_client, project_id)


def reset_sampling_rules_cache() -> None:
    with _sampling_snapshot_cache_lock:
        _sampling_snapshot_cache.clear()
        _sampling_cache_generation.clear()


def _filter_rules_for_consumer(
    rules: list[tsi.SamplingRuleSchema],
    consumer: tsi.SamplingConsumer,
    monitor_id: str | None,
) -> list[tsi.SamplingRuleSchema]:
    if consumer == "sdk":
        return [rule for rule in rules if not rule.scope.startswith(MONITOR_SCOPE_PREFIX)]
    if consumer == "monitor":
        if monitor_id is None:
            return rules
        monitor_scope = f"{MONITOR_SCOPE_PREFIX}{monitor_id}"
        return [
            rule
            for rule in rules
            if rule.scope.startswith(PROJECT_SCOPE_PREFIX) or rule.scope == monitor_scope
        ]
    raise ValueError(f"Unknown sampling consumer: {consumer}")


def _cache_key(
    project_id: str, consumer: tsi.SamplingConsumer, monitor_id: str | None
) -> tuple[str, tsi.SamplingConsumer, str | None]:
    return (project_id, consumer, monitor_id)


def _cache_generation(project_id: str) -> int:
    with _sampling_snapshot_cache_lock:
        return _sampling_cache_generation.get(project_id, 0)


def _redis_cache_key(
    project_id: str, consumer: tsi.SamplingConsumer, monitor_id: str | None
) -> str:
    monitor_part = monitor_id or "_"
    return f"{REDIS_SAMPLING_KEY_PREFIX}{consumer}:{project_id}:{monitor_part}"


def _l1_get(
    project_id: str, consumer: tsi.SamplingConsumer, monitor_id: str | None
) -> tsi.SamplingRulesSnapshotRes | None:
    with _sampling_snapshot_cache_lock:
        return _sampling_snapshot_cache.get(_cache_key(project_id, consumer, monitor_id))


def _l1_set(
    project_id: str,
    consumer: tsi.SamplingConsumer,
    monitor_id: str | None,
    snapshot: tsi.SamplingRulesSnapshotRes,
) -> None:
    with _sampling_snapshot_cache_lock:
        _sampling_snapshot_cache[_cache_key(project_id, consumer, monitor_id)] = snapshot


def _l2_get(
    redis_client: redis.Redis,
    project_id: str,
    consumer: tsi.SamplingConsumer,
    monitor_id: str | None,
) -> tsi.SamplingRulesSnapshotRes | None:
    try:
        raw = redis_client.get(_redis_cache_key(project_id, consumer, monitor_id))
        if raw is None:
            return None
        if not isinstance(raw, (str, bytes, bytearray)):
            return None
        return tsi.SamplingRulesSnapshotRes.model_validate_json(raw)
    except (redis.RedisError, TypeError, UnicodeDecodeError, ValidationError, ValueError):
        logger.exception("Redis sampling cache read failed for project %s", project_id)
    return None


def _l2_set(
    redis_client: redis.Redis,
    snapshot: tsi.SamplingRulesSnapshotRes,
    consumer: tsi.SamplingConsumer,
    monitor_id: str | None,
) -> None:
    try:
        redis_client.set(
            _redis_cache_key(snapshot.project_id, consumer, monitor_id),
            snapshot.model_dump_json(),
            ex=REDIS_SAMPLING_EXPIRY_SECS,
        )
    except (redis.RedisError, TypeError, ValueError):
        logger.exception(
            "Redis sampling cache write failed for project %s", snapshot.project_id
        )


def _l2_delete_project(redis_client: redis.Redis, project_id: str) -> None:
    try:
        pattern = f"{REDIS_SAMPLING_KEY_PREFIX}*:{project_id}:*"
        keys = list(redis_client.scan_iter(match=pattern))
        if keys:
            redis_client.delete(*keys)
    except redis.RedisError:
        logger.exception("Redis sampling cache delete failed for project %s", project_id)


def _coerce_datetime(value: datetime.datetime | str) -> datetime.datetime:
    if isinstance(value, datetime.datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=datetime.timezone.utc)
        return value
    return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
