"""Shared fixtures for trace tests."""

from __future__ import annotations

import pytest

from tests.trace.test_utils import FailingSaveType, failing_load, failing_save
from weave.trace.serialization import serializer
from weave.trace_server import environment as wf_env

# Tests that hit known distributed-mode production bugs. Each entry maps the
# qualified test name (path + ::node) to a one-line reason. These are skipped
# only when WF_CLICKHOUSE_USE_DISTRIBUTED_TABLES is true; they pass on cloud
# (single-node) and single-shard replicated topologies. Trim this list as the
# underlying bugs land in follow-up PRs.
_DISTRIBUTED_KNOWN_FAILURES: dict[str, str] = {
    # `globalIn` auto-rewrite under CH 25.11 + distributed_product_mode=global
    # emits a per-shard subquery where CH then complains 'Invalid local IN
    # function name globalIn'. Filed for trace_server query builder follow-up.
    "tests/trace/test_client_filter_calls_by_refs.py::test_filter_calls_by_ref_properties": "globalIn",
    "tests/trace/test_client_filter_calls_by_refs.py::test_filter_calls_by_ref_properties_with_table_rows_simple": "globalIn",
    "tests/trace/test_client_filter_calls_by_refs.py::test_mixed_objects_and_refs": "globalIn",
    # llm_token_prices is rand-sharded so the per-shard cost JOIN misses rows
    # that hashed to a different shard; same root cause as the OTEL cost test
    # already skipped in distributed mode.
    "tests/trace/test_client_trace.py::test_read_call_start_with_cost": "cost JOIN cross-shard",
    "tests/trace/test_client_cost.py::test_cost_apis": "cost JOIN cross-shard + DELETE on Distributed",
    "tests/trace/test_client_cost.py::test_purge_only_ids": "DELETE on Distributed (llm_token_prices)",
    "tests/trace/test_weave_client.py::test_summary_tokens_cost": "cost JOIN cross-shard",
    # feedback_purge / feedback_replace issue DELETE against the Distributed
    # wrapper for `feedback`; mirrors the annotation_queues lightweight UPDATE
    # bug. Needs the same caller-resolves-_local pattern applied to ORM purges.
    "tests/trace/test_client_feedback.py::test_feedback_apis": "DELETE on Distributed (feedback)",
    "tests/trace/test_feedback.py::test_client_feedback": "DELETE on Distributed (feedback)",
    "tests/trace/test_feedback.py::test_feedback_replace": "DELETE on Distributed (feedback)",
    # OPTIMIZE TABLE is unsupported on Distributed engine; storage-size tests
    # need to target `_local` on cluster the same way force_optimize_calls_merged
    # already does.
    "tests/trace/test_client_trace.py::test_calls_query_with_storage_size_clickhouse": "OPTIMIZE on Distributed",
    "tests/trace/test_client_trace.py::test_calls_query_with_total_storage_size_clickhouse": "OPTIMIZE on Distributed",
    "tests/trace/test_client_trace.py::test_calls_query_with_both_storage_sizes_clickhouse": "OPTIMIZE on Distributed",
    "tests/trace/test_client_trace.py::test_call_query_stream_with_costs_and_storage_size": "OPTIMIZE on Distributed",
    "tests/trace/test_client_trace.py::test_calls_query_stats_total_storage_size_clickhouse": "OPTIMIZE on Distributed",
    "tests/trace/test_weave_client.py::test_get_calls_storage_size_values": "OPTIMIZE on Distributed",
}


def pytest_collection_modifyitems(config, items):
    """Skip distributed-mode known-failures when running against a distributed cluster."""
    if not wf_env.wf_clickhouse_use_distributed_tables():
        return
    skip_distributed = pytest.mark.skip
    for item in items:
        nodeid = item.nodeid
        # Strip parametrize suffix so the bare test id matches the map.
        base = nodeid.split("[")[0]
        reason = _DISTRIBUTED_KNOWN_FAILURES.get(base) or _DISTRIBUTED_KNOWN_FAILURES.get(nodeid)
        if reason:
            item.add_marker(skip_distributed(reason=f"distributed-mode known failure: {reason}"))


@pytest.fixture
def failing_serializer():
    """Register a serializer that always fails, and clean up after the test."""
    serializer.register_serializer(FailingSaveType, failing_save, failing_load)
    yield FailingSaveType
    serializer.SERIALIZERS[:] = [
        s for s in serializer.SERIALIZERS if s.target_class is not FailingSaveType
    ]
