from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

from pydantic import BaseModel
from rich.table import Table

from weave.trace import urls
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
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.interface.builtin_object_classes.saved_view import Column, Pin
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
    # TODO: wb_user_id
    # TODO: wb_run_id
]

COLUMN_ALIASES = {
    "Status": "summary.weave.status",
}

# This needs to be kept in sync with the type of the direction field of tsi.SortBy
SortDirection = Literal["asc", "desc"]


class Filter(BaseModel):
    field: str
    # Type of operator could be locked down more, but this is better for extensibility
    operator: str
    value: Any


Filters = list[Filter]


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


EVALUATE_OP_NAME_POST_PYDANTIC = "Evaluation.evaluate"


def make_eval_op_name(entity: str, project: str) -> str:
    return f"weave:///{entity}/{project}/op/{EVALUATE_OP_NAME_POST_PYDANTIC}:*"


DEFAULT_PIN = Pin(left=["CustomCheckbox", "op_name"], right=[])

# Map from the user input operator string to a Material UI like operator string.
OPERATOR_MAP = {
    "contains": "(string): contains",
    "does not contain": "(string): notContains",
    "equals": "(string): equals",
    "does not equal": "(string): notEquals",
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

VALUELESS_OPERATORS = {"(any): isEmpty", "(any): isNotEmpty"}

# We return a real float from the backend! do not convert to double!
# When option clicking latency, because we are generating this field
# manually on the backend, it is actually a float, not a string stored
# in json, so we need to omit the conversion params from the filter
FIELDS_NO_FLOAT_CONVERT = {"summary.weave.latency_ms"}


def py_to_api_filter(filter: tsi.CallsFilter | None) -> tsi.CallsFilter | None:
    """Convert Saved View Filter to API Filter"""
    if filter is None:
        return None
    return tsi.CallsFilter(
        **filter.model_dump(exclude_none=True),
    )


# See operationConverter in weave-js
def get_field_expression(field: str) -> dict[str, Any]:
    """Helper function to get field expression based on whether it needs float conversion."""
    if field in FIELDS_NO_FLOAT_CONVERT:
        return {"$getField": field}
    return {"$convert": {"input": {"$getField": field}, "to": "double"}}


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
    elif item.operator == "(string): notContains":
        return {
            "$not": [
                {
                    "$contains": {
                        "input": {"$getField": item.field},
                        "substr": {"$literal": item.value},
                    },
                }
            ],
        }
    elif item.operator == "(string): equals":
        return {
            "$eq": [{"$getField": item.field}, {"$literal": item.value}],
        }
    elif item.operator == "(string): notEquals":
        return {
            "$not": [
                {
                    "$eq": [{"$getField": item.field}, {"$literal": item.value}],
                }
            ],
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
        field = get_field_expression(item.field)
        return {"$eq": [field, {"$literal": value}]}
    elif item.operator == "(number): !=":
        value = float(item.value)
        field = get_field_expression(item.field)
        return {"$not": [{"$eq": [field, {"$literal": value}]}]}
    elif item.operator == "(number): >":
        value = float(item.value)
        field = get_field_expression(item.field)
        return {"$gt": [field, {"$literal": value}]}
    elif item.operator == "(number): >=":
        value = float(item.value)
        field = get_field_expression(item.field)
        return {"$gte": [field, {"$literal": value}]}
    elif item.operator == "(number): <":
        value = float(item.value)
        field = get_field_expression(item.field)
        return {"$not": [{"$gte": [field, {"$literal": value}]}]}
    elif item.operator == "(number): <=":
        value = float(item.value)
        field = get_field_expression(item.field)
        return {"$not": [{"$gt": [field, {"$literal": value}]}]}
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
    """Convert in-memory only Filters to API Query."""
    if not filters:
        return None

    filter_clauses = [filter_to_clause(f) for f in filters]
    expr = {"$and": filter_clauses}
    return tsi.Query(**{"$expr": expr})


class QueryTranslationException(Exception):
    """Exception raised when a query cannot be translated to or from filters."""

    pass


def operand_to_filter_eq(operand: tsi_query.EqOperation) -> Filter:
    first = operand.eq_[0]
    second = operand.eq_[1]
    if isinstance(first, tsi_query.ConvertOperation) and first.convert_.to in (
        "double",
        "int",
    ):
        first = first.convert_.input
    if isinstance(first, tsi_query.GetFieldOperator) and isinstance(
        second, tsi_query.LiteralOperation
    ):
        value = second.literal_
        if isinstance(value, str):
            if value == "":
                operator = "(any): isEmpty"
                value = None
            else:
                operator = "(string): equals"
        elif isinstance(value, (int, float)):
            operator = "(number): ="
        else:
            raise QueryTranslationException(f"Could not parse {operand}")
        field = first.get_field_
        return Filter(field=field, operator=operator, value=value)
    raise QueryTranslationException(f"Could not parse {operand}")


def operand_to_filter_contains(operand: tsi_query.ContainsOperation) -> Filter:
    input = operand.contains_.input
    substr = operand.contains_.substr
    case_insensitive = operand.contains_.case_insensitive
    # TODO: Handle case_insensitive correctly
    if isinstance(input, tsi_query.GetFieldOperator) and isinstance(
        substr, tsi_query.LiteralOperation
    ):
        value = substr.literal_
        if isinstance(value, str):
            operator = "(string): contains"
        else:
            raise QueryTranslationException(f"Could not parse {operand}")
        field = input.get_field_
        return Filter(field=field, operator=operator, value=value)
    raise QueryTranslationException(f"Could not parse {operand}")


def operand_to_filter_gt(operand: tsi_query.GtOperation) -> Filter:
    first = operand.gt_[0]
    second = operand.gt_[1]
    if isinstance(first, tsi_query.ConvertOperation) and first.convert_.to in (
        "double",
        "int",
    ):
        first = first.convert_.input
    if isinstance(first, tsi_query.GetFieldOperator) and isinstance(
        second, tsi_query.LiteralOperation
    ):
        value = second.literal_
        if isinstance(value, (int, float)):
            operator = "(number): >"
        else:
            raise QueryTranslationException(f"Could not parse {operand}")
        field = first.get_field_
        if field == "started_at":
            operator = "(date): after"
            value = datetime.fromtimestamp(value).isoformat()
        return Filter(field=field, operator=operator, value=value)
    raise QueryTranslationException(f"Could not parse {operand}")


def operand_to_filter_gte(operand: tsi_query.GteOperation) -> Filter:
    first = operand.gte_[0]
    second = operand.gte_[1]
    if isinstance(first, tsi_query.ConvertOperation) and first.convert_.to in (
        "double",
        "int",
    ):
        first = first.convert_.input
    if isinstance(first, tsi_query.GetFieldOperator) and isinstance(
        second, tsi_query.LiteralOperation
    ):
        value = second.literal_
        if isinstance(value, (int, float)):
            operator = "(number): >="
        else:
            raise QueryTranslationException(f"Could not parse {operand}")
        field = first.get_field_
        return Filter(field=field, operator=operator, value=value)
    raise QueryTranslationException(f"Could not parse {operand}")


def operand_to_filter(operand: tsi_query.Operand) -> Filter:
    if isinstance(operand, tsi_query.EqOperation):
        return operand_to_filter_eq(operand)
    if isinstance(operand, tsi_query.ContainsOperation):
        return operand_to_filter_contains(operand)
    if isinstance(operand, tsi_query.GtOperation):
        return operand_to_filter_gt(operand)
    if isinstance(operand, tsi_query.GteOperation):
        return operand_to_filter_gte(operand)
    if isinstance(operand, tsi_query.NotOperation):
        filter = operand_to_filter(operand.not_[0])
        if filter.operator == "(number): >=":
            filter.operator = "(number): <"
        elif filter.operator == "(number): >":
            filter.operator = "(number): <="
        elif filter.operator == "(number): =":
            filter.operator = "(number): !="
        elif filter.operator == "(string): equals":
            filter.operator = "(string): notEquals"
        elif filter.operator == "(string): notEquals":
            filter.operator = "(string): equals"
        elif filter.operator == "(string): contains":
            filter.operator = "(string): notContains"
        elif filter.operator == "(string): notContains":
            filter.operator = "(string): contains"
        elif filter.operator == "(date): after":
            filter.operator = "(date): before"
        elif filter.operator == "(date): before":
            filter.operator = "(date): after"
        elif filter.operator == "(any): isEmpty":
            filter.operator = "(any): isNotEmpty"
        elif filter.operator == "(any): isNotEmpty":
            filter.operator = "(any): isEmpty"
        else:
            raise QueryTranslationException(f"Could not parse {filter}")
        return filter
    if isinstance(operand, tsi_query.OrOperation):
        if len(operand.or_) > 0:
            operands = [operand_to_filter(o) for o in operand.or_]
            if all(o.field == operands[0].field for o in operands):
                if all(o.operator == "(string): equals" for o in operands):
                    operator = "(string): in"
                    value = [o.value for o in operands]
                    return Filter(
                        field=operands[0].field, operator=operator, value=value
                    )
    raise QueryTranslationException(f"Could not parse {operand}")


def query_to_filters(query: tsi.Query | None) -> Filters | None:
    """Convert Saved View Query to Filters representation."""
    if query is None:
        return None

    if isinstance(query.expr_, tsi_query.AndOperation):
        operands = query.expr_.and_
        if not operands:
            return None
        return [operand_to_filter(o) for o in operands]

    if (
        isinstance(query.expr_, tsi_query.EqOperation)
        or isinstance(query.expr_, tsi_query.GtOperation)
        or isinstance(query.expr_, tsi_query.GteOperation)
        or isinstance(query.expr_, tsi_query.NotOperation)
        or isinstance(query.expr_, tsi_query.ContainsOperation)
    ):
        return [operand_to_filter(query.expr_)]

    raise QueryTranslationException(f"Could not parse {query}")


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


def render_status(value: Any) -> str:
    if value == tsi.TraceStatus.SUCCESS:
        return "✅"
    elif value == tsi.TraceStatus.ERROR:
        return "❌"
    elif value == tsi.TraceStatus.RUNNING:
        return "⏳"
    return value


def render_cell(path: ObjectPath, value: Any) -> str:
    if path.elements[0] == "op_name":
        op_ref = parse_op_uri(value)
        return op_ref.name
    if path == ObjectPath(["summary", "weave", "status"]):
        return render_status(value)
    return value


class SavedView:
    """A fluent-style class for working with SavedView objects."""

    base: SavedViewBase
    ref: ObjectRef | None = None

    def __init__(self, view_type: str = "traces", label: str = "SavedView") -> None:
        self.base = SavedViewBase(
            view_type=view_type,
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

    def add_filter(
        self, field: str, operator: str, value: Any | None = None
    ) -> SavedView:
        if field in COLUMN_ALIASES:
            field = COLUMN_ALIASES[field]
        if ObjectPath.parse_str(field).elements[0] not in KNOWN_COLUMNS:
            raise ValueError(f'Column "{field}" is not known')
        op = OPERATOR_MAP.get(operator)
        if not op:
            raise ValueError(f"Operator {operator} not supported")
        if op in VALUELESS_OPERATORS and value is not None:
            raise ValueError(f"Operator {operator} does not support a value")
        if op not in VALUELESS_OPERATORS and value is None:
            raise ValueError(f"Operator {operator} requires a value")
        new_filter = Filter(field=field, operator=op, value=value)
        filters = query_to_filters(self.base.definition.query) or []
        if new_filter in filters:
            # Already have a matching filter, don't add a duplicate.
            return self
        filters.append(new_filter)
        self.base.definition.query = filters_to_query(filters)
        return self

    def remove_filter(self, index_or_field: int | str) -> SavedView:
        query = self.base.definition.query
        filters = query_to_filters(query)
        if not filters:
            return self
        if isinstance(index_or_field, int):
            filters.pop(index_or_field)
        else:
            filters = [f for f in filters if f.field != index_or_field]
        if filters:
            self.base.definition.query = filters_to_query(filters)
        else:
            self.base.definition.query = None
        return self

    def remove_filters(self) -> SavedView:
        """Remove all filters from the saved view."""
        self.base.definition.query = None
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
                self.base.definition.filter = tsi.CallsFilter()
            self.base.definition.filter.op_names = [op_uri]
        return self

    def add_sort(self, field: str, direction: SortDirection) -> SavedView:
        if self.base.definition.sort_by is None:
            self.base.definition.sort_by = []
        clause = tsi.SortBy(field=field, direction=direction)
        self.base.definition.sort_by.append(clause)
        return self

    def sort_by(self, field: str, direction: SortDirection) -> SavedView:
        self.base.definition.sort_by = []
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
        # TODO: If no columns have been specified in the view should we start from the default list?
        if isinstance(path, str) and path in COLUMN_ALIASES:
            if label is None:
                label = path
            path = COLUMN_ALIASES[path]
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
            if path in COLUMN_ALIASES:
                if label is None:
                    label = path
                path = COLUMN_ALIASES[path]
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
            if path in COLUMN_ALIASES:
                path = COLUMN_ALIASES[path]
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
            if path in COLUMN_ALIASES:
                path = COLUMN_ALIASES[path]
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
    def label(self) -> str:
        return self.base.label

    @property
    def view_type(self) -> str:
        return self.base.view_type

    def ui_url(self) -> str | None:
        """URL to show this saved view in the UI.

        Note this is the "result" page with traces etc, not the URL for the view object."""
        if self.ref and self.entity and self.project:
            weave_root = urls.project_weave_root_url(self.entity, self.project)
            return f"{weave_root}/{self.view_type}?view={self.ref.name}"
        return None

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
        table.add_row("Name", self.label)
        if self.base.description is not None:
            table.add_row("Description", self.base.description)
        if self.ref:
            table.add_row("URL", self.ui_url())
            table.add_row("Ref", self.ref.uri())
        table.add_row("View type", self.view_type)
        if self.base.definition.filter is not None:
            table.add_row(
                "Call Filter",
                pydantic_util.model_to_table(
                    self.base.definition.filter, filter_none_values=True
                ),
            )
        if self.base.definition.query is not None:
            try:
                filters = query_to_filters(self.base.definition.query)
                if filters:
                    filters_table = Table()
                    filters_table.add_column("Field")
                    filters_table.add_column("Operator")
                    filters_table.add_column("Value")
                    for filter in filters:
                        filters_table.add_row(
                            filter.field, filter.operator, str(filter.value)
                        )
                    table.add_row("Filters", filters_table)
            except QueryTranslationException:
                table.add_row("Query", str(self.base.definition.query))

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
        if self.base.definition.sort_by is not None:
            values = [f"{s.field} {s.direction}" for s in self.base.definition.sort_by]
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
            name = f"{self.view_type}_{formatted_now}"
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

            # For evaluations, inject a frozen filter.
            filter = self.base.definition.filter
            if self.view_type == "evaluations":
                filter = filter.model_copy() if filter else tsi.CallsFilter()
                filter.op_names = [make_eval_op_name(client.entity, client.project)]

            query = self.base.definition.query
            sort_by = self.base.definition.sort_by
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

        # Fallback to column visibility specification
        visibility = self.base.definition.cols or {}
        default_column_paths = [
            "id",
            "summary.weave.trace_name",
            "summary.weave.status",
            "started_at",
        ]
        # Add any columns that are visible that are not in the above list
        for key, value in visibility.items():
            if value and key not in default_column_paths:
                if ObjectPath.parse_str(key).elements[0] in KNOWN_COLUMNS:
                    default_column_paths.append(key)
        pin: Pin = self.base.definition.pin or DEFAULT_PIN
        for pin_right in pin["right"]:
            # If a column is pinned to the right, move it to the end of the list
            if pin_right in default_column_paths:
                default_column_paths.remove(pin_right)
                default_column_paths.append(pin_right)
        for pin_left in pin["left"]:
            # If a column is pinned to the left, move it to the start of the list
            if pin_left in default_column_paths:
                default_column_paths.remove(pin_left)
                default_column_paths.insert(0, pin_left)
        column_headers = {
            "id": "ID",
            "summary.weave.trace_name": "Trace",
            "summary.weave.status": "Status",
            "started_at": "Called",
        }

        default_columns: list[TableColumn] = []
        for path in default_column_paths:
            if not visibility.get(path, True):
                continue
            default_columns.append(
                {
                    "path": ObjectPath.parse_str(path),
                    "label": column_headers.get(path, path),
                }
            )

        # TODO: Handle inputs, output, attributes
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
