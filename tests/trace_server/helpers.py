"""Shared helpers for trace_server tests."""

import base64
import uuid

from clickhouse_connect.driver.client import Client as CHClient

from tests.trace.server_utils import find_server_layer
from weave.trace.weave_client import WeaveClient
from weave.trace_server import environment as wf_env
from weave.trace_server.clickhouse_trace_server_batched import ClickHouseTraceServer


def make_project_id(prefix: str) -> str:
    """Generate a unique base64-encoded project id for a test."""
    raw = f"test/{prefix}_{uuid.uuid4().hex[:8]}"
    return base64.b64encode(raw.encode()).decode()


def force_optimize(ch_client: CHClient, table: str) -> None:
    """OPTIMIZE `table` for test merge-consistency, distributed-mode aware.

    OPTIMIZE is not supported on Distributed engines; in distributed mode we
    target the underlying `_local` ReplicatedMergeTree on the cluster.
    """
    if wf_env.wf_clickhouse_use_distributed_tables():
        cluster = wf_env.wf_clickhouse_replicated_cluster()
        ch_client.command(f"OPTIMIZE TABLE {table}_local ON CLUSTER {cluster} FINAL")
    else:
        ch_client.command(f"OPTIMIZE TABLE {table} FINAL")


def force_optimize_calls_merged(ch_client: CHClient) -> None:
    """OPTIMIZE `calls_merged`, distributed-mode aware."""
    force_optimize(ch_client, "calls_merged")


def force_optimize_if_clickhouse(client: WeaveClient, table: str) -> None:
    """OPTIMIZE `table` when the client runs on ClickHouse; no-op otherwise.

    Lets tests that exercise both backends force ClickHouse merge-consistency
    without teaching `force_optimize` about non-ClickHouse servers. The
    in-memory fake has no async merges to force.
    """
    try:
        ch_server = find_server_layer(client.server, ClickHouseTraceServer)
    except TypeError:
        return
    force_optimize(ch_server.ch_client, table)
