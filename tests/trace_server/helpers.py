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


def seed_legacy_residence(ch_client: CHClient, project_id: str) -> str:
    """Insert one calls_merged row so V1 writes to `project_id` keep routing there.

    Returns the seeded call id so callers can exclude it from row assertions.
    """
    call_id = str(uuid.uuid4())
    ch_client.command(
        "INSERT INTO calls_merged (project_id, id, op_name, started_at, trace_id, parent_id) "
        "VALUES ({project_id:String}, {id:String}, 'seed', now(), {trace_id:String}, '')",
        parameters={
            "project_id": project_id,
            "id": call_id,
            "trace_id": str(uuid.uuid4()),
        },
    )

    return call_id


def force_optimize(ch_client: CHClient, table: str) -> None:
    """OPTIMIZE `table` for test merge-consistency, distributed-mode aware.

    OPTIMIZE is not supported on Distributed engines; in distributed mode we
    target the underlying `_local` ReplicatedMergeTree on the cluster, then
    SYNC REPLICA so the merged part is visible on whichever replica a later
    read is routed to.
    """
    if wf_env.wf_clickhouse_use_distributed_tables():
        cluster = wf_env.wf_clickhouse_replicated_cluster()
        ch_client.command(f"OPTIMIZE TABLE {table}_local ON CLUSTER {cluster} FINAL")
        ch_client.command(
            f"SYSTEM SYNC REPLICA ON CLUSTER {cluster} {ch_client.database}.{table}_local"
        )
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
