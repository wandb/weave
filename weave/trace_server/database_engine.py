"""ClickHouse database engine discovery for the migrator.

Queries ``system.databases`` to determine whether a database uses the
Replicated engine (DDL auto-replicated, ON CLUSTER forbidden) or the
default Atomic engine (explicit ON CLUSTER + ReplicatedMergeTree required).

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
