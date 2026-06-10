"""Shared helpers for trace_server tests."""

import base64
import uuid

from weave.trace_server import environment as wf_env


def make_project_id(prefix: str) -> str:
    """Generate a unique base64-encoded project id for a test."""
    raw = f"test/{prefix}_{uuid.uuid4().hex[:8]}"
    return base64.b64encode(raw.encode()).decode()


def force_optimize_table(ch_client, table: str = "calls_merged") -> None:
    """OPTIMIZE a calls table for test merge-consistency, distributed-mode aware.

    OPTIMIZE is not supported on Distributed engines; in distributed mode we
    target the underlying `_local` ReplicatedMergeTree on the cluster.
    """
    if wf_env.wf_clickhouse_use_distributed_tables():
        cluster = wf_env.wf_clickhouse_replicated_cluster()
        ch_client.command(f"OPTIMIZE TABLE {table}_local ON CLUSTER {cluster} FINAL")
    else:
        ch_client.command(f"OPTIMIZE TABLE {table} FINAL")
