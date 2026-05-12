from __future__ import annotations

import datetime
import fnmatch
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from weave.trace.refs import OpRef
from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)

SAMPLING_DECISION_ATTRIBUTE = "weave.sampling.decision"
SAMPLING_RULE_SCOPE_ATTRIBUTE = "weave.sampling.rule_scope"
SAMPLING_RULE_OP_PATTERN_ATTRIBUTE = "weave.sampling.rule_op_pattern"

SAMPLING_KEEP = "keep"
SAMPLING_DROP = "drop"

PROJECT_SCOPE_PREFIX = "project:"
MONITOR_SCOPE_PREFIX = "monitor:"

_MASK_64 = 0xFFFFFFFFFFFFFFFF
_XXH64_PRIME_1 = 11400714785074694791
_XXH64_PRIME_2 = 14029467366897019727
_XXH64_PRIME_3 = 1609587929392839161
_XXH64_PRIME_4 = 9650029242287828579
_XXH64_PRIME_5 = 2870177450012600261
_HASH_DENOMINATOR = float(1 << 64)


@dataclass(frozen=True)
class SamplingDecision:
    keep: bool
    rule: tsi.SamplingRuleSchema | None = None
    reason: str = "default_keep"
    hash_value: float | None = None

    @property
    def decision_attribute(self) -> str:
        return SAMPLING_KEEP if self.keep else SAMPLING_DROP


def default_sampling_snapshot(project_id: str) -> tsi.SamplingRulesSnapshotRes:
    now = datetime.datetime.now(datetime.timezone.utc)
    return tsi.SamplingRulesSnapshotRes(
        project_id=project_id,
        rules=[],
        etag=build_sampling_etag([]),
        snapshot_updated_at=now,
    )


def build_sampling_etag(rules: list[tsi.SamplingRuleSchema]) -> str:
    import hashlib
    import json

    identity_tuples = sorted(
        (rule.scope, rule.op_pattern, rule.rate) for rule in rules
    )
    payload = json.dumps(identity_tuples, separators=(",", ":"), sort_keys=True)
    return f"sha256-{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


def validate_glob_pattern(pattern: str) -> None:
    try:
        _compile_glob(pattern)
    except re.error as exc:
        raise ValueError(f"Invalid glob pattern {pattern!r}: {exc}") from exc


def decide_project_sampling(
    snapshot: tsi.SamplingRulesSnapshotRes | None,
    *,
    trace_id: str,
    op_name: str,
    attributes: dict[str, Any] | None = None,
) -> SamplingDecision:
    if snapshot is None or not snapshot.rules:
        return SamplingDecision(keep=True)
    if _is_exempt(snapshot, op_name, attributes or {}):
        return SamplingDecision(keep=True, reason="exempt")

    rule = find_matching_rule(snapshot.rules, op_name, scope_prefix=PROJECT_SCOPE_PREFIX)
    return _decision_for_rule(snapshot.project_id, trace_id, rule)


def decide_monitor_sampling(
    snapshot: tsi.SamplingRulesSnapshotRes | None,
    *,
    trace_id: str,
    op_name: str,
    monitor_id: str,
    attributes: dict[str, Any] | None = None,
) -> SamplingDecision:
    if snapshot is None or not snapshot.rules:
        return SamplingDecision(keep=True)
    if _is_exempt(snapshot, op_name, attributes or {}):
        return SamplingDecision(keep=True, reason="exempt")

    rule = find_matching_rule(
        snapshot.rules,
        op_name,
        exact_scope=f"{MONITOR_SCOPE_PREFIX}{monitor_id}",
    )
    return _decision_for_rule(snapshot.project_id, trace_id, rule)


def find_matching_rule(
    rules: list[tsi.SamplingRuleSchema],
    op_name: str,
    *,
    scope_prefix: str | None = None,
    exact_scope: str | None = None,
) -> tsi.SamplingRuleSchema | None:
    candidates: list[tuple[tuple[int, int, float, str], tsi.SamplingRuleSchema]] = []
    op_name_candidates = _op_name_candidates(op_name)
    for rule in rules:
        if exact_scope is not None and rule.scope != exact_scope:
            continue
        if scope_prefix is not None and not rule.scope.startswith(scope_prefix):
            continue
        specificity = _best_pattern_specificity(rule.op_pattern, op_name_candidates)
        if specificity is None:
            continue
        candidates.append(
            (
                (
                    specificity[0],
                    specificity[1],
                    _updated_at_sort_value(rule.updated_at),
                    rule.op_pattern,
                ),
                rule,
            )
        )
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[0])[1]


def apply_sampling_attributes(
    attributes: dict[str, Any], decision: SamplingDecision
) -> None:
    attributes[SAMPLING_DECISION_ATTRIBUTE] = decision.decision_attribute
    if decision.rule is not None:
        attributes[SAMPLING_RULE_SCOPE_ATTRIBUTE] = decision.rule.scope
        attributes[SAMPLING_RULE_OP_PATTERN_ATTRIBUTE] = decision.rule.op_pattern


def sampling_hash_ratio(
    *,
    trace_id: str,
    project_id: str,
    scope: str,
    op_pattern: str,
) -> float:
    identity = f"{trace_id}|{project_id}|{scope}|{op_pattern}"
    return xxh64_int(identity.encode("utf-8"), seed=0) / _HASH_DENOMINATOR


def xxh64_int(data: bytes, seed: int = 0) -> int:
    length = len(data)
    index = 0

    if length >= 32:
        v1 = (seed + _XXH64_PRIME_1 + _XXH64_PRIME_2) & _MASK_64
        v2 = (seed + _XXH64_PRIME_2) & _MASK_64
        v3 = seed & _MASK_64
        v4 = (seed - _XXH64_PRIME_1) & _MASK_64

        limit = length - 32
        while index <= limit:
            v1 = _xxh64_round(v1, _read_u64(data, index))
            index += 8
            v2 = _xxh64_round(v2, _read_u64(data, index))
            index += 8
            v3 = _xxh64_round(v3, _read_u64(data, index))
            index += 8
            v4 = _xxh64_round(v4, _read_u64(data, index))
            index += 8

        h64 = (
            _rotl64(v1, 1) + _rotl64(v2, 7) + _rotl64(v3, 12) + _rotl64(v4, 18)
        ) & _MASK_64
        h64 = _xxh64_merge_round(h64, v1)
        h64 = _xxh64_merge_round(h64, v2)
        h64 = _xxh64_merge_round(h64, v3)
        h64 = _xxh64_merge_round(h64, v4)
    else:
        h64 = (seed + _XXH64_PRIME_5) & _MASK_64

    h64 = (h64 + length) & _MASK_64

    while index <= length - 8:
        k1 = _xxh64_round(0, _read_u64(data, index))
        h64 ^= k1
        h64 = ((_rotl64(h64, 27) * _XXH64_PRIME_1) + _XXH64_PRIME_4) & _MASK_64
        index += 8

    if index <= length - 4:
        h64 ^= (_read_u32(data, index) * _XXH64_PRIME_1) & _MASK_64
        h64 = ((_rotl64(h64, 23) * _XXH64_PRIME_2) + _XXH64_PRIME_3) & _MASK_64
        index += 4

    while index < length:
        h64 ^= (data[index] * _XXH64_PRIME_5) & _MASK_64
        h64 = (_rotl64(h64, 11) * _XXH64_PRIME_1) & _MASK_64
        index += 1

    h64 ^= h64 >> 33
    h64 = (h64 * _XXH64_PRIME_2) & _MASK_64
    h64 ^= h64 >> 29
    h64 = (h64 * _XXH64_PRIME_3) & _MASK_64
    h64 ^= h64 >> 32
    return h64 & _MASK_64


def _decision_for_rule(
    project_id: str, trace_id: str, rule: tsi.SamplingRuleSchema | None
) -> SamplingDecision:
    if rule is None:
        return SamplingDecision(keep=True)
    hash_value = sampling_hash_ratio(
        trace_id=trace_id,
        project_id=project_id,
        scope=rule.scope,
        op_pattern=rule.op_pattern,
    )
    return SamplingDecision(
        keep=hash_value < rule.rate,
        rule=rule,
        reason="rule",
        hash_value=hash_value,
    )


def _is_exempt(
    snapshot: tsi.SamplingRulesSnapshotRes, op_name: str, attributes: dict[str, Any]
) -> bool:
    exemptions = snapshot.exemptions
    for pattern in exemptions.op_patterns:
        if _glob_matches(pattern, op_name):
            return True
    return any(_has_attribute_key(attributes, key) for key in exemptions.attribute_keys)


def _has_attribute_key(attributes: dict[str, Any], key: str) -> bool:
    if key in attributes:
        return True
    current: Any = attributes
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _pattern_specificity(pattern: str, op_name: str) -> tuple[int, int] | None:
    if pattern == "":
        return (0, 0)
    if pattern == op_name:
        return (2, len(pattern))
    if _has_glob_magic(pattern) and _glob_matches(pattern, op_name):
        return (1, _non_star_prefix_len(pattern))
    return None


def _best_pattern_specificity(
    pattern: str, op_name_candidates: tuple[str, ...]
) -> tuple[int, int] | None:
    specificities = [
        specificity
        for candidate in op_name_candidates
        if (specificity := _pattern_specificity(pattern, candidate)) is not None
    ]
    if not specificities:
        return None
    return max(specificities)


def _op_name_candidates(op_name: str) -> tuple[str, ...]:
    if not op_name.startswith("weave:///"):
        return (op_name,)
    try:
        op_ref = OpRef.parse_uri(op_name)
    except (TypeError, ValueError):
        return (op_name,)
    return (op_name, op_ref.name)


def _has_glob_magic(pattern: str) -> bool:
    return any(ch in pattern for ch in "*?[")


def _non_star_prefix_len(pattern: str) -> int:
    star_index = pattern.find("*")
    if star_index == -1:
        return len(pattern)
    return star_index


def _glob_matches(pattern: str, value: str) -> bool:
    if pattern == "":
        return True
    try:
        return bool(_compile_glob(pattern).match(value))
    except re.error:
        logger.warning("Ignoring invalid sampling glob pattern: %s", pattern)
        return False


@lru_cache(maxsize=1024)
def _compile_glob(pattern: str) -> re.Pattern[str]:
    return re.compile(fnmatch.translate(pattern))


def _updated_at_sort_value(value: datetime.datetime) -> float:
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.timezone.utc)
    return value.timestamp()


def _rotl64(value: int, bits: int) -> int:
    return ((value << bits) | (value >> (64 - bits))) & _MASK_64


def _read_u64(data: bytes, index: int) -> int:
    return int.from_bytes(data[index : index + 8], "little")


def _read_u32(data: bytes, index: int) -> int:
    return int.from_bytes(data[index : index + 4], "little")


def _xxh64_round(acc: int, lane: int) -> int:
    acc = (acc + lane * _XXH64_PRIME_2) & _MASK_64
    acc = _rotl64(acc, 31)
    acc = (acc * _XXH64_PRIME_1) & _MASK_64
    return acc


def _xxh64_merge_round(acc: int, value: int) -> int:
    acc ^= _xxh64_round(0, value)
    acc = ((acc * _XXH64_PRIME_1) + _XXH64_PRIME_4) & _MASK_64
    return acc
