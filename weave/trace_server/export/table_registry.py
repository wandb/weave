"""Closed-set mapping from the user-facing export table name to the concrete
CH table identifier and time column.

Identifiers in this registry are NEVER user-controlled; the SQL builder
inlines them as bare identifiers. Anything else has to come through CH
`{name:T}` parameter substitution.
"""

from dataclasses import dataclass
from typing import get_args

from weave.trace_server.export.schemas import ExportTable


@dataclass(frozen=True)
class TableSpec:
    """One row of the registry.

    Attributes:
        ch_table: bare identifier of the source table in CH.
        time_column: column name used for `time_range` filtering, or `None`
            if the table has no time order key (filter is silently dropped
            in that case; v1 only registers tables with a time column).
        project_id_column: column carrying the project id; always
            `project_id` today but kept explicit so future tables that use
            a different name (e.g. join views) slot in.
    """

    ch_table: str
    time_column: str
    project_id_column: str = "project_id"


TABLE_REGISTRY: dict[ExportTable, TableSpec] = {
    "calls_complete": TableSpec(ch_table="calls_complete", time_column="started_at"),
    "calls_merged": TableSpec(ch_table="calls_merged", time_column="started_at"),
}


def assert_registry_covers_literal() -> None:
    """Static check: every `ExportTable` literal must have a TABLE_REGISTRY row.

    Called at module import time so a literal added without a registry row
    fails loudly at startup instead of returning a 500 mid-request.
    """
    missing = set(get_args(ExportTable)) - set(TABLE_REGISTRY.keys())
    if missing:
        raise RuntimeError(
            f"ExportTable literals without TABLE_REGISTRY rows: {sorted(missing)}"
        )


assert_registry_covers_literal()
