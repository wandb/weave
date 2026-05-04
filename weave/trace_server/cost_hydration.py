import datetime
from bisect import bisect_right
from dataclasses import dataclass
from typing import Any

from weave.trace_server.token_costs import DEFAULT_PRICING_LEVEL_ID, PRICING_LEVELS


@dataclass(frozen=True)
class _PriceBucket:
    timestamps: list[float]
    rows: list[dict[str, Any]]


@dataclass(frozen=True)
class PriceIndex:
    project: _PriceBucket
    default: _PriceBucket
    other: _PriceBucket


def normalize_cost_datetime(
    value: datetime.datetime | str | None,
) -> datetime.datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.datetime.fromisoformat(value)
    if value.tzinfo is None:
        return value.replace(tzinfo=datetime.timezone.utc)
    return value.astimezone(datetime.timezone.utc)


def cost_usage_from_summary(
    summary: dict[str, Any] | None,
) -> dict[str, dict[str, int]]:
    usage_map = (summary or {}).get("usage")
    if not isinstance(usage_map, dict):
        return {}

    normalized_usage: dict[str, dict[str, int]] = {}
    for llm_id, usage in usage_map.items():
        if not isinstance(usage, dict):
            continue
        normalized_usage[str(llm_id)] = {
            "prompt_tokens": _safe_int(usage.get("prompt_tokens"))
            + _safe_int(usage.get("input_tokens")),
            "completion_tokens": _safe_int(usage.get("completion_tokens"))
            + _safe_int(usage.get("output_tokens")),
            "requests": _safe_int(usage.get("requests")),
            "total_tokens": _safe_int(usage.get("total_tokens")),
            "cache_read_input_tokens": _safe_int(
                usage.get("cache_read_input_tokens")
            ),
            "cache_creation_input_tokens": _safe_int(
                usage.get("cache_creation_input_tokens")
            ),
        }
    return normalized_usage


def build_price_indexes(
    price_rows: list[dict[str, Any]], project_id: str
) -> dict[str, PriceIndex]:
    grouped: dict[str, dict[str, list[tuple[float, dict[str, Any]]]]] = {}

    for row in price_rows:
        effective_date = normalize_cost_datetime(row.get("effective_date"))
        if effective_date is None:
            continue
        llm_id = str(row["llm_id"])
        bucket_name = _price_bucket_name(row, project_id)
        grouped.setdefault(
            llm_id,
            {
                "project": [],
                "default": [],
                "other": [],
            },
        )[bucket_name].append((effective_date.timestamp(), row))

    indexes: dict[str, PriceIndex] = {}
    for llm_id, buckets in grouped.items():
        indexes[llm_id] = PriceIndex(
            project=_make_price_bucket(buckets["project"]),
            default=_make_price_bucket(buckets["default"]),
            other=_make_price_bucket(buckets["other"]),
        )
    return indexes


def hydrate_calls_with_costs(
    calls: list[dict[str, Any]],
    price_indexes: dict[str, PriceIndex],
) -> None:
    usage_by_call_id: dict[str, dict[str, dict[str, int]]] = {}
    for call in calls:
        summary = call.get("summary")
        if not isinstance(summary, dict):
            continue
        usage_by_model = cost_usage_from_summary(summary)
        if usage_by_model:
            usage_by_call_id[call["id"]] = usage_by_model

    if not usage_by_call_id:
        return

    for call in calls:
        summary = call.get("summary")
        if not isinstance(summary, dict):
            continue

        weave_summary = summary.get("weave")
        if not isinstance(weave_summary, dict):
            weave_summary = {}
            summary["weave"] = weave_summary
        else:
            weave_summary.pop("costs", None)

        started_at = normalize_cost_datetime(call.get("started_at"))
        if started_at is None:
            continue

        call_costs: dict[str, dict[str, Any]] = {}
        for llm_id, usage in usage_by_call_id.get(call["id"], {}).items():
            best_row = pick_best_cost_row(price_indexes.get(llm_id), started_at)
            if best_row is None:
                continue
            call_costs[llm_id] = build_cost_entry(usage, best_row)

        if call_costs:
            weave_summary["costs"] = call_costs


def pick_best_cost_row(
    index: PriceIndex | None, started_at: datetime.datetime
) -> dict[str, Any] | None:
    if index is None:
        return None

    started_ts = started_at.timestamp()
    for bucket in (index.project, index.default, index.other):
        row = _latest_at_or_before(bucket, started_ts)
        if row is not None:
            return row

    for bucket in (index.project, index.default, index.other):
        row = _latest_future(bucket, started_ts)
        if row is not None:
            return row

    return None


def build_cost_entry(
    usage: dict[str, int],
    price_row: dict[str, Any],
) -> dict[str, Any]:
    prompt_cost = _safe_float(price_row.get("prompt_token_cost"))
    completion_cost = _safe_float(price_row.get("completion_token_cost"))
    cache_read_cost = _safe_float(price_row.get("cache_read_input_token_cost"))
    cache_creation_cost = _safe_float(
        price_row.get("cache_creation_input_token_cost")
    )
    prompt_tokens = usage["prompt_tokens"]
    completion_tokens = usage["completion_tokens"]
    cache_read_input_tokens = usage.get("cache_read_input_tokens", 0)
    cache_creation_input_tokens = usage.get("cache_creation_input_tokens", 0)

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cache_read_input_tokens": cache_read_input_tokens,
        "cache_creation_input_tokens": cache_creation_input_tokens,
        "requests": usage["requests"],
        "total_tokens": usage["total_tokens"],
        "prompt_tokens_total_cost": (
            prompt_tokens - cache_read_input_tokens - cache_creation_input_tokens
        )
        * prompt_cost,
        "completion_tokens_total_cost": completion_tokens * completion_cost,
        "cache_read_input_tokens_total_cost": cache_read_input_tokens
        * cache_read_cost,
        "cache_creation_input_tokens_total_cost": cache_creation_input_tokens
        * cache_creation_cost,
        "prompt_token_cost": prompt_cost,
        "completion_token_cost": completion_cost,
        "cache_read_input_token_cost": cache_read_cost,
        "cache_creation_input_token_cost": cache_creation_cost,
        "prompt_token_cost_unit": price_row.get("prompt_token_cost_unit"),
        "completion_token_cost_unit": price_row.get("completion_token_cost_unit"),
        "effective_date": _serialize_cost_metadata(price_row.get("effective_date")),
        "provider_id": price_row.get("provider_id"),
        "pricing_level": price_row.get("pricing_level"),
        "pricing_level_id": price_row.get("pricing_level_id"),
        "created_at": _serialize_cost_metadata(price_row.get("created_at")),
        "created_by": price_row.get("created_by"),
    }


def _price_bucket_name(row: dict[str, Any], project_id: str) -> str:
    if (
        row.get("pricing_level") == PRICING_LEVELS["PROJECT"]
        and row.get("pricing_level_id") == project_id
    ):
        return "project"
    if (
        row.get("pricing_level") == PRICING_LEVELS["DEFAULT"]
        and row.get("pricing_level_id") == DEFAULT_PRICING_LEVEL_ID
    ):
        return "default"
    return "other"


def _make_price_bucket(rows: list[tuple[float, dict[str, Any]]]) -> _PriceBucket:
    rows = sorted(rows, key=lambda item: item[0])
    return _PriceBucket(
        timestamps=[item[0] for item in rows],
        rows=[item[1] for item in rows],
    )


def _latest_at_or_before(
    bucket: _PriceBucket, started_ts: float
) -> dict[str, Any] | None:
    idx = bisect_right(bucket.timestamps, started_ts) - 1
    if idx >= 0:
        return bucket.rows[idx]
    return None


def _latest_future(bucket: _PriceBucket, started_ts: float) -> dict[str, Any] | None:
    if bucket.timestamps and bucket.timestamps[-1] > started_ts:
        return bucket.rows[-1]
    return None


def _safe_int(value: Any) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _serialize_cost_metadata(value: Any) -> Any:
    if isinstance(value, datetime.datetime):
        normalized = normalize_cost_datetime(value)
        assert normalized is not None
        millis = normalized.microsecond // 1000
        return f"{normalized:%Y-%m-%d %H:%M:%S}.{millis:03d}"
    return value
