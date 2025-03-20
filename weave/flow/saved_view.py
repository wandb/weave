from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from rich.table import Table

from weave.trace.api import publish as weave_publish
from weave.trace.api import ref as weave_ref
from weave.trace.context import weave_client_context
from weave.trace.grid import Grid
from weave.trace.refs import ObjectRef, parse_op_uri
from weave.trace.rich import pydantic_util
from weave.trace.traverse import ObjectPath, get_paths
from weave.trace.vals import WeaveObject
from weave.trace.weave_client import CallsIter
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.builtin_object_classes.saved_view import (
    CallsFilter,
    Column,
    Filter,
    Filters,
    Pin,
    SortBy,
    SortDirection,
)
from weave.trace_server.interface.builtin_object_classes.saved_view import (
    SavedView as SavedViewBase,
)

KNOWN_COLUMNS = [
    "id",
    "display_name",
    "op_name",
    "inputs",
    "output",
    "attributes",
    "summary",
    "started_at",
    "ended_at",
    "exception",
    "func_name",
    "parent_id",
    "project_id",
    "trace_id",
    "ui_url",
    # TODO: feedback
    # TODO: status
    # TODO: wb_user_id
    # TODO: wb_run_id
]


class TableColumn(TypedDict):
    """A column in a table view."""

    path: ObjectPath
    label: str


def to_seconds(value: Any) -> float | None:
    """Convert a value to seconds.

    This is used for constructing time based filters, but might belong
    in a more general purpose utility module.

    TODO: other date specifier strings like devtools?

    Handles:
    - None: returns None
    - Empty string: returns None
    - Numbers: returns the number directly
    - Strings that can be parsed as numbers: returns the parsed number
    - Date strings: parses as date and returns seconds since epoch
    - datetime objects: returns seconds since epoch

    Returns:
        float | None: The value converted to seconds, or None if conversion failed
    """
    if value is None or value == "":
        return None

    # If it's already a number, return it directly
    if isinstance(value, (int, float)):
        return float(value)

    # Try to parse as a number
    try:
        return float(value)
    except (ValueError, TypeError):
        pass

    # Try to parse as a date
    try:
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


DEFAULT_PIN = Pin(left=["CustomCheckbox", "op_name"], right=[])
DEFAULT_FILTER = Filters(items=[], logicOperator="and")

# Map from the user input operator string to a Material UI like operator string.
OPERATOR_MAP = {
    "contains": "(string): contains",
    "equals": "(string): equals",
    "in": "(string): in",
    "=": "(number): =",
    "≠": "(number): !=",
    "!=": "(number): !=",
    "<": "(number): <",
    "≤": "(number): <=",
    "<=": "(number): <=",
    ">": "(number): >",
    "≥": "(number): >=",
    ">=": "(number): >=",
    "is": "(bool): is",
    "after": "(date): after",
    "before": "(date): before",
    "is empty": "(any): isEmpty",
    "is not empty": "(any): isNotEmpty",
}


def py_to_api_filter(filter: CallsFilter | None) -> tsi.CallsFilter | None:
    """Convert Saved View Filter to API Filter"""
    if filter is None:
        return None
    return tsi.CallsFilter(
        **filter.model_dump(exclude_none=True),
    )


def py_to_api_sort_by(sort_by: list[SortBy] | None) -> list[tsi.SortBy] | None:
    """Convert Saved View SortBy to API SortBy"""
    if sort_by is None:
        return None
    return [tsi.SortBy(field=s.field, direction=s.direction) for s in sort_by]


# See operationConverter in weave-js
def filter_to_clause(item: Filter) -> dict[str, Any]:
    if item.operator == "(any): isEmpty":
        return {
            "$eq": [{"$getField": item.field}, {"$literal": ""}],
        }
    elif item.operator == "(any): isNotEmpty":
        return {
            "$not": [
                {
                    "$eq": [{"$getField": item.field}, {"$literal": ""}],
                },
            ],
        }
    elif item.operator == "(string): contains":
        return {
            "$contains": {
                "input": {"$getField": item.field},
                "substr": {"$literal": item.value},
            },
        }
    elif item.operator == "(string): equals":
        return {
            "$eq": [{"$getField": item.field}, {"$literal": item.value}],
        }
    elif item.operator == "(string): in":
        values = (
            item.value
            if isinstance(item.value, list)
            else [s.strip() for s in item.value.split(",")]
        )
        clauses = [
            {"$eq": [{"$getField": item.field}, {"$literal": v}]} for v in values
        ]
        return {"$or": clauses}
    elif item.operator == "(number): =":
        value = float(item.value)
        return {
            "$eq": [
                {"$convert": {"input": {"$getField": item.field}, "to": "double"}},
                {"$literal": value},
            ],
        }
    elif item.operator == "(number): !=":
        value = float(item.value)
        return {
            "$not": [
                {
                    "$eq": [
                        {
                            "$convert": {
                                "input": {"$getField": item.field},
                                "to": "double",
                            }
                        },
                        {"$literal": value},
                    ],
                },
            ],
        }
    elif item.operator == "(number): >":
        value = float(item.value)
        return {
            "$gt": [
                {"$convert": {"input": {"$getField": item.field}, "to": "double"}},
                {"$literal": value},
            ],
        }
    elif item.operator == "(number): >=":
        value = float(item.value)
        return {
            "$gte": [
                {"$convert": {"input": {"$getField": item.field}, "to": "double"}},
                {"$literal": value},
            ],
        }
    elif item.operator == "(number): <":
        value = float(item.value)
        return {
            "$not": [
                {
                    "$gte": [
                        {
                            "$convert": {
                                "input": {"$getField": item.field},
                                "to": "double",
                            }
                        },
                        {"$literal": value},
                    ],
                }
            ],
        }
    elif item.operator == "(number): <=":
        value = float(item.value)
        return {
            "$not": [
                {
                    "$gt": [
                        {
                            "$convert": {
                                "input": {"$getField": item.field},
                                "to": "double",
                            }
                        },
                        {"$literal": value},
                    ],
                }
            ],
        }
    elif item.operator == "(bool): is":
        return {
            "$eq": [{"$getField": item.field}, {"$literal": str(item.value)}],
        }
    elif item.operator == "(date): after":
        seconds = to_seconds(item.value)
        if seconds is None:
            raise ValueError(f"Invalid date value: {item.value}")
        return {
            "$gt": [{"$getField": item.field}, {"$literal": seconds}],
        }
    elif item.operator == "(date): before":
        seconds = to_seconds(item.value)
        if seconds is None:
            raise ValueError(f"Invalid date value: {item.value}")
        return {
            "$not": [
                {
                    "$gt": [{"$getField": item.field}, {"$literal": seconds}],
                },
            ],
        }
    else:
        raise ValueError(f"Unsupported operator: {item.operator}")


def filters_to_query(filters: Filters | None) -> tsi.Query | None:
    """Convert Saved View Filters to API Filters"""
    if filters is None or not filters.items:
        return None

    # TODO: Handle additional logicOperator's
    filter_clauses = [filter_to_clause(f) for f in filters.items]
    expr = {"$and": filter_clauses}
    return tsi.Query(**{"$expr": expr})


def get_object_path(obj: WeaveObject, path: str | ObjectPath) -> Any:
    """Given a path and an object, return what is pointed to."""
    if isinstance(path, str):
        path = ObjectPath.parse_str(path)
    if not isinstance(path[0], str):
        raise TypeError(f"Path must start with a string, got {path[0]}")
    result = getattr(obj, path[0])
    for element in path[1:]:
        if result is None:
            return None
        if isinstance(result, dict):
            result = result.get(element, None)
        else:
            try:
                result = result[element]
            except (IndexError, KeyError):
                return None
    return result


def render_cell(path: ObjectPath, value: Any) -> str:
    if path.elements[0] == "op_name":
        op_ref = parse_op_uri(value)
        return op_ref.name
    return value


class SavedView:
    """A fluent-style class for working with SavedView objects."""

    base: SavedViewBase
    ref: ObjectRef | None = None

    def __init__(self, table: str = "traces", label: str = "SavedView") -> None:
        self.base = SavedViewBase(
            table=table,
            label=label,
            definition={},
        )

    @property
    def entity(self) -> str | None:
        if self.ref:
            return self.ref.entity
        client = weave_client_context.get_weave_client()
        return client.entity if client else None

    @property
    def project(self) -> str | None:
        if self.ref:
            return self.ref.project
        client = weave_client_context.get_weave_client()
        return client.project if client else None

    def rename(self, label: str) -> SavedView:
        self.base.label = label
        return self

    def add_filter(self, field: str, operator: str, value: Any) -> SavedView:
        if ObjectPath.parse_str(field).elements[0] not in KNOWN_COLUMNS:
            raise ValueError(f'Column "{field}" is not known')
        op = OPERATOR_MAP.get(operator)
        if not op:
            raise ValueError(f"Operator {operator} not supported")
        if not self.base.definition.filters:
            self.base.definition.filters = DEFAULT_FILTER.model_copy()
        assert self.base.definition.filters is not None
        next_id = len(self.base.definition.filters.items)
        filter = Filter(id=next_id, field=field, operator=op, value=value)
        self.base.definition.filters.items.append(filter)
        return self

    def remove_filter(self, index_or_field: int | str) -> SavedView:
        if not self.base.definition.filters or not self.base.definition.filters.items:
            return self
        if isinstance(index_or_field, int):
            self.base.definition.filters.items.pop(index_or_field)
        else:
            self.base.definition.filters.items = [
                f
                for f in self.base.definition.filters.items
                if f.field != index_or_field
            ]
        if not self.base.definition.filters.items:
            self.base.definition.filters = None
        return self

    def remove_filters(self) -> SavedView:
        """Remove all filters from the saved view."""
        self.base.definition.filters = None
        return self

    def _check_empty_call_filter(self) -> None:
        """If all of the call filters are None, remove it."""
        if self.base.definition.filter:
            # Check if all fields in the filter are None
            filter_fields = self.base.definition.filter.model_dump()
            all_none = all(value is None for value in filter_fields.values())
            if all_none:
                self.base.definition.filter = None

    # TODO: Support other call filters such as parent_ids, call_ids, etc.

    def filter_op(self, op_name: str | None) -> SavedView:
        if op_name is None:
            if self.base.definition.filter:
                self.base.definition.filter.op_names = None
                self._check_empty_call_filter()
        else:
            op_uri = op_name
            if not op_uri.startswith("weave:///"):
                if not self.entity:
                    raise ValueError(
                        "Must specify Op URI if entity/project is not known"
                    )
                op_uri = f"weave:///{self.entity}/{self.project}/op/{op_name}"
                if ":" not in op_name:
                    op_uri += ":*"
            if not self.base.definition.filter:
                self.base.definition.filter = CallsFilter()
            self.base.definition.filter.op_names = [op_uri]
        return self

    def add_sort(self, field: str, direction: SortDirection) -> SavedView:
        if self.base.definition.sort is None:
            self.base.definition.sort = []
        clause = SortBy(field=field, direction=direction)
        self.base.definition.sort.append(clause)
        return self

    def sort_by(self, field: str, direction: SortDirection) -> SavedView:
        self.base.definition.sort = []
        return self.add_sort(field, direction)

    # Showing and hiding columns this way is not preferred.
    # Instead try specifying exactly which columns to include.
    def show_column(self, col_name: str) -> SavedView:
        if not self.base.definition.cols:
            self.base.definition.cols = {}
        self.base.definition.cols[col_name] = True
        return self

    def hide_column(self, col_name: str) -> SavedView:
        if not self.base.definition.cols:
            self.base.definition.cols = {}
        self.base.definition.cols[col_name] = False
        return self

    def add_column(self, path: str | ObjectPath, label: str | None = None) -> SavedView:
        idx = len(self.base.definition.columns) if self.base.definition.columns else 0
        return self.insert_column(idx, path, label)

    def add_columns(self, *columns: str) -> SavedView:
        """Convenience method for adding multiple columns to the grid."""
        for column in columns:
            self.add_column(column)
        return self

    def insert_column(
        self, idx: int, path: str | ObjectPath, label: str | None = None
    ) -> SavedView:
        if isinstance(path, str):
            path = ObjectPath.parse_str(path)
        # We only check the first element in case the user knows better than us
        # what columns are possible (e.g. an input that doesn't appear in first page of calls)
        if path[0] not in KNOWN_COLUMNS:
            raise ValueError(f'Column "{path}" is not known')
        # Note: Currently allowing adding the same column multiple times, maybe we shouldn't.
        if not self.base.definition.columns:
            self.base.definition.columns = []
        self.base.definition.columns.insert(idx, Column(path=path, label=label))
        return self

    def set_columns(self, *columns: str) -> SavedView:
        """Set the columns to be displayed in the grid."""
        self.base.definition.columns = []
        self.add_columns(*columns)
        return self

    def column_index(self, path: int | str | ObjectPath) -> int:
        if isinstance(path, str):
            path = ObjectPath.parse_str(path)
        for i, col in enumerate(self.get_table_columns()):
            if col["path"] == path:
                return i
        if isinstance(path, int):
            if path < 0 or path >= len(self.get_table_columns()):
                raise ValueError(f'Column index "{path}" out of bounds')
            return path
        raise ValueError(f'Column "{path}" not found')

    def rename_column(self, path: int | str | ObjectPath, label: str) -> SavedView:
        index = self.column_index(path)
        assert self.base.definition.columns is not None
        self.base.definition.columns[index].label = label
        return self

    def remove_column(self, path: int | str | ObjectPath) -> SavedView:
        if isinstance(path, str):
            path = ObjectPath.parse_str(path)
        if not self.base.definition.columns:
            return self
        if isinstance(path, int):
            self.base.definition.columns.pop(path)
            return self
        self.base.definition.columns = [
            col
            for col in self.base.definition.columns
            if not col.path or col.path != path.elements
        ]
        if not self.base.definition.columns:
            self.base.definition.columns = None
        return self

    def remove_columns(self, *columns: str) -> SavedView:
        """Remove columns from the saved view."""
        if not columns:
            self.base.definition.columns = None
            return self
        for col in columns:
            self.remove_column(col)
        return self

    def pin_column_left(self, col_name: str) -> SavedView:
        if not self.base.definition.pin:
            self.base.definition.pin = DEFAULT_PIN.model_copy()
        assert self.base.definition.pin is not None
        if col_name in self.base.definition.pin.right:
            self.base.definition.pin.right.remove(col_name)
        if col_name not in self.base.definition.pin.left:
            self.base.definition.pin.left.append(col_name)
        return self

    def pin_column_right(self, col_name: str) -> SavedView:
        if not self.base.definition.pin:
            self.base.definition.pin = DEFAULT_PIN.model_copy()
        assert self.base.definition.pin is not None
        if col_name in self.base.definition.pin.left:
            self.base.definition.pin.left.remove(col_name)
        if col_name not in self.base.definition.pin.right:
            self.base.definition.pin.right.append(col_name)
        return self

    def unpin_column(self, col_name: str) -> SavedView:
        if not self.base.definition.pin:
            self.base.definition.pin = DEFAULT_PIN.copy()
        assert self.base.definition.pin is not None
        if col_name in self.base.definition.pin.left:
            self.base.definition.pin.left.remove(col_name)
        elif col_name in self.base.definition.pin.right:
            self.base.definition.pin.right.remove(col_name)
        return self

    def page_size(self, page_size: int) -> SavedView:
        self.base.definition.page_size = page_size
        return self

    @property
    def name(self) -> str:
        return self.base.label

    @property
    def table(self) -> str:
        return self.base.table

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text("SavedView(...)")
        else:
            p.text(self.to_rich_table_str())

    def to_rich_table_str(self) -> str:
        table = Table(show_header=False)
        table.add_column("Key", justify="right", style="bold cyan")
        table.add_column("Value")
        table.add_row("Name", self.name)
        if self.base.description is not None:
            table.add_row("Description", self.base.description)
        if self.ref:
            table.add_row("Ref", self.ref.uri())
        table.add_row("Table", self.base.table)
        if self.base.definition.filter is not None:
            table.add_row(
                "Call Filter",
                pydantic_util.model_to_table(
                    self.base.definition.filter, filter_none_values=True
                ),
            )
        if self.base.definition.filters is not None:
            filters_table = Table()
            filters_table.add_column("Field")
            filters_table.add_column("Operator")
            filters_table.add_column("Value")
            for filter in self.base.definition.filters.items:
                filters_table.add_row(filter.field, filter.operator, str(filter.value))
            table.add_row("Filters", filters_table)
        if self.base.definition.columns is not None:
            columns_table = Table()
            columns_table.add_column("Column")
            columns_table.add_column("Label")
            for col in self.base.definition.columns:
                columns_table.add_row(ObjectPath(col.path).to_str(), col.label)
            table.add_row("Columns", columns_table)
        if self.base.definition.cols:
            # Create a nested table for column visibility
            # TODO: Maybe color the boolean value?
            cols_table = Table()
            cols_table.add_column("Column")
            cols_table.add_column("Show")
            for col_id, visible in self.base.definition.cols.items():
                cols_table.add_row(col_id, str(visible))
            table.add_row("Column Visibility", cols_table)
        if self.base.definition.pin is not None:
            value = pydantic_util.model_to_table(self.base.definition.pin)
            table.add_row("Pin", value)
        if self.base.definition.sort is not None:
            values = [f"{s.field} {s.direction}" for s in self.base.definition.sort]
            table.add_row("Sort", ", ".join(values))
        if self.base.definition.page_size is not None:
            table.add_row("Page Size", str(self.base.definition.page_size))
        return pydantic_util.table_to_str(table)

    def __str__(self) -> str:
        return self.to_rich_table_str()

    def save(self) -> SavedView:
        """Publish the saved view to the server."""
        name = self.base.name
        if name is None:
            formatted_now = (
                datetime.now()
                .isoformat()
                .replace("T", "_")
                .replace(":", "-")
                .replace(".", "-")[:-1]
            )
            name = f"{self.base.table}_{formatted_now}"
        self.ref = weave_publish(self.base, name)
        return self

    def get_calls(
        self,
        limit: int | None = None,
        offset: int | None = None,
        include_costs: bool = False,
        include_feedback: bool = False,
        all_columns: bool = False,
    ) -> CallsIter:
        """Get calls matching this saved view's filters and settings."""
        entity = self.ref.entity if self.ref else None
        project = self.ref.project if self.ref else None
        with weave_client_context.with_weave_client(
            entity=entity, project=project
        ) as client:
            assert client is not None  # with_weave_client would have raised
            # This method is also used internally, we allow forcing all columns.
            table_columns = None if all_columns else self.get_table_columns()
            if table_columns:
                columns = [c["path"].to_str() for c in table_columns]
            else:
                columns = None
            query = filters_to_query(self.base.definition.filters)
            filter = py_to_api_filter(self.base.definition.filter)
            sort_by = py_to_api_sort_by(self.base.definition.sort)
            return client.get_calls(
                columns=columns,
                query=query,
                filter=filter,
                sort_by=sort_by,
                limit=limit,
                offset=offset,
                include_costs=include_costs,
                include_feedback=include_feedback,
            )

    def to_grid(self, limit: int | None = None) -> Grid:
        calls = list(self.get_calls(limit=limit))
        columns = self.get_table_columns()
        grid = Grid()
        for col in columns:
            # TODO: Should we have a sort indictor in the column header?
            grid.add_column(col["label"])
        for call in calls:
            row = []
            for col in columns:
                # TODO: Custom rendering for some columns
                value = get_object_path(call, col["path"])
                value = render_cell(col["path"], value)
                row.append(value)
            grid.add_row(row)
        return grid

    def get_known_columns(self, *, num_calls_to_query: int | None = None) -> list[str]:
        """Get the set of columns that are known to exist."""
        # TODO: Would be nice if we had a more efficient way to query server for this.
        limit = num_calls_to_query or 10
        seen = set(KNOWN_COLUMNS)
        if weave_client_context.get_weave_client() is not None:
            for call in self.get_calls(limit=limit, all_columns=True):
                seen.update(p.to_str() for p in get_paths(call.to_dict()))
        return sorted(seen)

    def get_table_columns(self) -> list[TableColumn]:
        # If columns are defined in the saved view definition, use those directly
        if self.base.definition.columns:
            return [
                {
                    "path": ObjectPath(col.path),
                    "label": col.label
                    or (ObjectPath(col.path).to_str() if col.path else ""),
                }
                for col in self.base.definition.columns
            ]
        default_columns: list[TableColumn] = [
            {
                "path": ObjectPath(["id"]),
                "label": "ID",
            },
        ]
        # TODO: Handle inputs, output, attributes
        # TODO: Handle visibility
        # TODO: Handle pinning
        return default_columns

    @classmethod
    def load(cls, ref: str) -> SavedView:
        obj_ref = weave_ref(ref)
        base = obj_ref.get()
        instance = cls.__new__(cls)
        instance.ref = obj_ref
        instance.base = base
        return instance

    # TODO: Where should we put method to list SavedViews?
    # TODO: View deletion
