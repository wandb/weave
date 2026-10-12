"""Canonical queries for managed-bucket bulk export targets.

Every query is project-scoped with the bound ClickHouse parameter
``{project_id:String}``. Calls follow the project's canonical storage routing,
while objects and feedback have one physical source each.
"""

from weave.trace_server.project_version.types import ReadTable

EXPORT_TARGET_NAMES = frozenset({"calls", "objects", "feedback"})


def build_export_query(target_name: str, calls_read_table: ReadTable) -> str:
    """Build one target query after the project's calls table is resolved."""
    if target_name == "calls":
        return build_calls_export_query(calls_read_table)
    if target_name == "objects":
        return build_objects_export_query()
    if target_name == "feedback":
        return build_feedback_export_query()
    raise ValueError(f"unknown export target {target_name!r}")


def build_calls_export_query(read_table: ReadTable) -> str:
    """Export raw physical call rows from the project's canonical table.

    ``calls_merged.display_name`` is an AggregateFunction state, which Parquet
    cannot encode. Finalizing that one cell type preserves the physical rows:
    there is deliberately no GROUP BY, FINAL, deduplication, or tombstone filter.
    """
    if read_table == ReadTable.CALLS_COMPLETE:
        return "SELECT * FROM calls_complete WHERE project_id = {project_id:String}"
    if read_table == ReadTable.CALLS_MERGED:
        return (
            "SELECT * EXCEPT (display_name), "
            "finalizeAggregation(display_name) AS display_name "
            "FROM calls_merged WHERE project_id = {project_id:String}"
        )
    raise ValueError(f"unsupported calls read table {read_table!r}")


def build_objects_export_query() -> str:
    """Export the visible newest row for each object version."""
    return (
        "SELECT * EXCEPT (rn) FROM ("
        "SELECT *, row_number() OVER ("
        "PARTITION BY project_id, kind, object_id, digest "
        "ORDER BY created_at DESC, (deleted_at IS NULL) ASC) AS rn "
        "FROM object_versions WHERE project_id = {project_id:String}"
        ") WHERE rn = 1 AND deleted_at IS NULL"
    )


def build_feedback_export_query() -> str:
    """Export feedback rows; feedback deletion is a physical DELETE."""
    return "SELECT * FROM feedback WHERE project_id = {project_id:String}"
