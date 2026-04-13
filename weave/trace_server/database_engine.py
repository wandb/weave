"""ClickHouse database engine and cluster discovery for the migrator.

Queries ``system.databases`` to determine whether a database uses the
Replicated engine (DDL auto-replicated, ON CLUSTER forbidden) or the
default Atomic engine (explicit ON CLUSTER + ReplicatedMergeTree required).

Queries ``system.clusters`` to detect the number of shards in a cluster,
which is used to auto-detect whether distributed tables are needed
(shards > 1 means data is split across nodes and requires Distributed engine tables).

Handles the metadata-visibility lag that can occur after ``CREATE DATABASE``
by polling with exponential back-off.
"""

import logging

from clickhouse_connect.driver.client import Client as CHClient
from tenacity import (
    RetryError,
    Retrying,
    retry_if_result,
    stop_after_delay,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Back-off configuration for waiting on system.databases visibility after
# CREATE DATABASE.
ENGINE_DISCOVERY_INITIAL_DELAY_SECONDS = 0.1
ENGINE_DISCOVERY_MAX_WAIT_SECONDS = 3.0
ENGINE_DISCOVERY_MAX_DELAY_SECONDS = 0.8

ENGINE_QUERY = "SELECT engine FROM system.databases WHERE name = %(db_name)s"

# Query to count distinct shards in a ClickHouse cluster.
# system.clusters contains one row per (shard, replica) pair, so counting
# distinct shard_num gives us the number of shards.
# A cluster with >1 shard needs Distributed engine tables to route queries
# across shards; a single-shard cluster only needs replicated tables.
CLUSTER_SHARD_COUNT_QUERY = (
    "SELECT count(DISTINCT shard_num) FROM system.clusters"
    " WHERE cluster = %(cluster_name)s"
)


class EngineDiscoveryError(RuntimeError):
    """Raised when a database engine cannot be determined."""


def get_database_engine(
    ch_client: CHClient,
    db_name: str,
) -> str | None:
    """Return the engine name for *db_name*, or ``None`` if it is not yet visible.

    Raises ``EngineDiscoveryError`` if the query itself fails (e.g. missing
    permissions on ``system.databases``).
    """
    try:
        result = ch_client.query(
            ENGINE_QUERY,
            parameters={"db_name": db_name},
        )
    except Exception as exc:
        raise EngineDiscoveryError(
            f"Could not determine database engine for `{db_name}` from "
            "system.databases. Replicated and distributed migrations "
            f"require SELECT access to system.databases. Underlying error: {exc}"
        ) from exc

    result_rows = getattr(result, "result_rows", None)
    if not isinstance(result_rows, list | tuple) or not result_rows:
        return None

    first_row = result_rows[0]
    if not isinstance(first_row, list | tuple) or not first_row:
        return None

    engine = first_row[0]
    return engine if isinstance(engine, str) else str(engine)


def wait_for_database_engine(
    ch_client: CHClient,
    db_name: str,
    max_wait_seconds: float = ENGINE_DISCOVERY_MAX_WAIT_SECONDS,
    context: str | None = None,
) -> str:
    """Poll ``system.databases`` until the engine for *db_name* is visible.

    Uses exponential back-off starting at
    ``ENGINE_DISCOVERY_INITIAL_DELAY_SECONDS``.  Raises
    ``EngineDiscoveryError`` after *max_wait_seconds* if the engine never
    appears.

    *context* is optional human-readable text (e.g. the SQL that created the
    database) included in the timeout error message for diagnostics.
    """
    retrying = Retrying(
        retry=retry_if_result(lambda result: result is None),
        wait=wait_exponential(
            multiplier=ENGINE_DISCOVERY_INITIAL_DELAY_SECONDS,
            max=ENGINE_DISCOVERY_MAX_DELAY_SECONDS,
        ),
        stop=stop_after_delay(max_wait_seconds),
        reraise=True,
    )

    try:
        engine = retrying(get_database_engine, ch_client, db_name)
    except RetryError as exc:
        context_clause = f" after executing `{context}`" if context else ""
        stats = retrying.statistics
        raise EngineDiscoveryError(
            f"Could not determine database engine for `{db_name}` after "
            f"{stats.get('attempt_number', '?')} attempts over "
            f"{max_wait_seconds:.1f}s{context_clause}."
        ) from exc

    if retrying.statistics.get("attempt_number", 1) > 1:
        stats = retrying.statistics
        logger.info(
            "Detected ClickHouse database engine for `%s` after %s "
            "attempts over %.2fs: %s",
            db_name,
            stats.get("attempt_number", "?"),
            stats.get("delay_since_first_attempt", 0),
            engine,
        )

    return engine


def detect_cluster_shard_count(
    ch_client: CHClient,
    cluster_name: str,
) -> int:
    """Return the number of distinct shards in *cluster_name*.

    Queries ClickHouse's ``system.clusters`` table which contains one row
    per (shard, replica) pair. Counting distinct ``shard_num`` tells us
    how many shards the cluster is configured with:

    - **1 shard**: all replicas hold the same data → distributed tables
      are unnecessary, plain ReplicatedMergeTree is sufficient.
    - **>1 shards**: data is partitioned across nodes → Distributed engine
      tables are needed to fan out queries and route inserts.

    Returns 0 if the cluster name is not found (e.g. single-node setup
    with no cluster configured).

    Raises ``EngineDiscoveryError`` if the query fails (e.g. missing
    SELECT access on ``system.clusters``).
    """
    try:
        result = ch_client.query(
            CLUSTER_SHARD_COUNT_QUERY,
            parameters={"cluster_name": cluster_name},
        )
    except Exception as exc:
        raise EngineDiscoveryError(
            f"Could not query system.clusters for cluster `{cluster_name}`. "
            "Auto-detection of distributed mode requires SELECT access to "
            f"system.clusters. Underlying error: {exc}"
        ) from exc

    # Extract the scalar count from the result.
    # Result shape: [[count]] — a single row with a single column.
    result_rows = getattr(result, "result_rows", None)
    if not isinstance(result_rows, list | tuple) or not result_rows:
        # No rows means the cluster name wasn't found in system.clusters.
        return 0

    first_row = result_rows[0]
    if not isinstance(first_row, list | tuple) or not first_row:
        return 0

    count = first_row[0]
    # Guard against None (e.g. from a mock or unexpected query result).
    if count is None:
        return 0
    return int(count)
