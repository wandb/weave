"""Table-aware field base classes for query builder."""

import re
from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict

from weave.trace_server.calls_query_builder.table_strategy import TableStrategy
from weave.trace_server.calls_query_builder.utils import (
    json_dump_field_as_sql,
    param_slot,
)
from weave.trace_server.errors import InvalidFieldError
from weave.trace_server.interface import query as tsi_query
from weave.trace_server.orm import (
    ParamBuilder,
    clickhouse_cast,
    split_escaped_field_path,
)

STORAGE_SIZE_TABLE_NAME = "storage_size_tbl"
ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME = "rolled_up_cms"


class QueryField(ABC):
    """Abstract base class defining the contract for all query fields.

    This allows any table backend to define its own field implementations
    while maintaining a consistent interface for the query builder.
    """

    field: str

    @abstractmethod
    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        """Generate SQL expression for this field.

        Args:
            pb: Parameter builder for safe parameterization
            table_alias: Alias of the table in the FROM clause
            cast: Optional type casting specification
            use_agg_fn: Whether to use aggregation function (for grouped queries)

        Returns:
            SQL expression string (e.g., "calls_merged.op_name" or "any(op_name)")
        """
        ...

    @abstractmethod
    def as_select_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        """Generate SQL for SELECT clause including alias.

        Returns:
            SQL with alias (e.g., "any(op_name) AS op_name")
        """
        ...

    @abstractmethod
    def is_heavy(self) -> bool:
        """Whether this field is expensive to compute."""
        ...

    @abstractmethod
    def supports_aggregation(self) -> bool:
        """Whether this field supports aggregation functions."""
        ...

    @abstractmethod
    def as_sql_without_aggregation(
        self,
        pb: ParamBuilder,
        table_alias: str,
    ) -> str:
        """Generate SQL without aggregation (for WHERE clauses)."""
        ...


class SimpleField(QueryField, BaseModel):
    """A basic field that maps directly to a column.

    Works for both aggregated and non-aggregated tables.
    The strategy determines whether to wrap with aggregation function.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    field: str
    agg_fn: str | None = None

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        base_sql = f"{table_alias}.{self.field}"

        if cast:
            base_sql = clickhouse_cast(base_sql, cast)

        return base_sql

    def as_select_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        return f"{self.as_sql(pb, table_alias)} AS {self.field}"

    def is_heavy(self) -> bool:
        return False

    def supports_aggregation(self) -> bool:
        """Whether this field can be used with aggregate functions."""
        return self.agg_fn is not None

    def as_sql_without_aggregation(
        self,
        pb: ParamBuilder,
        table_alias: str,
    ) -> str:
        """Generate SQL without aggregation function.

        Useful for WHERE clause conditions that need raw column access.
        """
        return f"{table_alias}.{self.field}"


class SimpleCallsField(SimpleField):
    strategy: TableStrategy

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        base_sql = f"{table_alias}.{self.field}"

        if self.strategy.requires_grouping() and self.agg_fn and use_agg_fn:
            base_sql = f"{self.agg_fn}({base_sql})"

        if cast:
            base_sql = clickhouse_cast(base_sql, cast)

        return base_sql

    def supports_aggregation(self) -> bool:
        return self.agg_fn is not None and self.strategy.requires_grouping()


class DynamicField(QueryField, BaseModel):
    """A field that supports JSON path navigation.

    Example: inputs.messages[0].content

    Works for both aggregated and non-aggregated tables.
    Use DynamicCallsField for strategy-aware aggregation.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    field: str
    agg_fn: str | None = None
    extra_path: list[str] | None = None

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        base_sql = f"{table_alias}.{self.field}"
        root_field_sanitized = base_sql

        return json_dump_field_as_sql(
            pb=pb,
            table_alias=table_alias,
            root_field_sanitized=root_field_sanitized,
            extra_path=self.extra_path,
            cast=cast,
            use_agg_fn=use_agg_fn,
        )

    def as_select_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        if self.extra_path:
            raise NotImplementedError(
                "Dynamic fields cannot be selected directly, yet - implement me!"
            )
        # For select without extra_path, just return the field
        base_sql = f"{table_alias}.{self.field}"
        return f"{base_sql} AS {self.field}"

    def is_heavy(self) -> bool:
        return True

    def with_path(self, path: list[str]) -> "DynamicField":
        extra_path = [*(self.extra_path or [])]
        extra_path.extend(path)
        return DynamicField(
            field=self.field,
            agg_fn=self.agg_fn,
            extra_path=extra_path,
        )

    def supports_aggregation(self) -> bool:
        """Whether this field can be used with aggregate functions."""
        return self.agg_fn is not None

    def as_sql_without_aggregation(
        self,
        pb: ParamBuilder,
        table_alias: str,
    ) -> str:
        """Generate SQL without aggregation function.

        Useful for WHERE clause conditions that need raw column access.
        """
        root_field_sanitized = f"{table_alias}.{self.field}"
        return json_dump_field_as_sql(
            pb=pb,
            table_alias=table_alias,
            root_field_sanitized=root_field_sanitized,
            extra_path=self.extra_path,
            cast=None,
            use_agg_fn=False,
        )


class DynamicCallsField(DynamicField):
    """DynamicField with strategy-aware aggregation."""

    strategy: TableStrategy

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        base_sql = f"{table_alias}.{self.field}"

        if self.strategy.requires_grouping() and self.agg_fn and use_agg_fn:
            root_field_sanitized = f"{self.agg_fn}({base_sql})"
        else:
            root_field_sanitized = base_sql

        return json_dump_field_as_sql(
            pb=pb,
            table_alias=table_alias,
            root_field_sanitized=root_field_sanitized,
            extra_path=self.extra_path,
            cast=cast,
            use_agg_fn=use_agg_fn,
        )

    def as_select_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        if self.extra_path:
            raise NotImplementedError(
                "Dynamic fields cannot be selected directly, yet - implement me!"
            )
        # For select without extra_path, just return the aggregated field
        base_sql = f"{table_alias}.{self.field}"
        if self.strategy.requires_grouping() and self.agg_fn:
            base_sql = f"{self.agg_fn}({base_sql})"
        return f"{base_sql} AS {self.field}"

    def with_path(self, path: list[str]) -> "DynamicCallsField":
        extra_path = [*(self.extra_path or [])]
        extra_path.extend(path)
        return DynamicCallsField(
            field=self.field,
            strategy=self.strategy,
            agg_fn=self.agg_fn,
            extra_path=extra_path,
        )

    def supports_aggregation(self) -> bool:
        """Whether this field can be used with aggregate functions."""
        return self.agg_fn is not None and self.strategy.requires_grouping()


class FieldWithTableOverride(SimpleCallsField):
    """Field that comes from a specific table (e.g., for JOINs)."""

    table_name: str | None = None

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        effective_alias = self.table_name if self.table_name else table_alias
        return super().as_sql(pb, effective_alias, cast, use_agg_fn)


class SummaryField(QueryField, BaseModel):
    """Field class for computed summary values."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    field: str
    strategy: TableStrategy
    summary_field: str

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        from weave.trace_server.calls_query_builder.calls_query_builder import (
            get_summary_field_handler,
        )

        handler = get_summary_field_handler(self.summary_field)
        if not handler:
            from weave.trace_server.calls_query_builder.calls_query_builder import (
                SUMMARY_FIELD_HANDLERS,
            )

            supported_fields = ", ".join(SUMMARY_FIELD_HANDLERS.keys())
            raise NotImplementedError(
                f"Summary field '{self.summary_field}' not implemented. "
                f"Supported fields are: {supported_fields}"
            )

        sql = handler(pb, table_alias, self.strategy.read_table_enum)
        return clickhouse_cast(sql, cast)

    def as_select_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        return f"{self.as_sql(pb, table_alias)} AS {self.field}"

    def is_heavy(self) -> bool:
        return False

    def supports_aggregation(self) -> bool:
        return False

    def as_sql_without_aggregation(
        self,
        pb: ParamBuilder,
        table_alias: str,
    ) -> str:
        return self.as_sql(pb, table_alias)


class FeedbackField(QueryField, BaseModel):
    """Field class for feedback payload fields."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    field: str
    strategy: TableStrategy
    feedback_type: str
    extra_path: list[str]

    @classmethod
    def from_path(cls, path: str, strategy: TableStrategy) -> "FeedbackField":
        """Expected format: `[feedback.type].dot.path`.

        feedback.type can be '*' to select all feedback types.
        """
        regex = re.compile(r"^(\[.+\])\.(.+)$")
        match = regex.match(path)
        if not match:
            raise InvalidFieldError(f"Invalid feedback path: {path}")
        feedback_type, path_str = match.groups()
        if feedback_type[0] != "[" or feedback_type[-1] != "]":
            raise InvalidFieldError(f"Invalid feedback type: {feedback_type}")
        extra_path = split_escaped_field_path(path_str)
        feedback_type = feedback_type[1:-1]

        if extra_path[0] == "payload":
            return cls(
                field="payload_dump",
                strategy=strategy,
                feedback_type=feedback_type,
                extra_path=extra_path[1:],
            )
        elif extra_path[0] == "runnable_ref":
            return cls(
                field="runnable_ref",
                strategy=strategy,
                feedback_type=feedback_type,
                extra_path=[],
            )
        elif extra_path[0] == "trigger_ref":
            return cls(
                field="trigger_ref",
                strategy=strategy,
                feedback_type=feedback_type,
                extra_path=[],
            )
        raise InvalidFieldError(f"Invalid feedback path: {path}")

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        inner = f"feedback.{self.field}"

        # Use aggregate functions only when use_agg_fn is True
        if use_agg_fn:
            if self.feedback_type == "*":
                res = f"any({inner})"
            else:
                param_name = pb.add_param(self.feedback_type)
                res = f"anyIf({inner}, feedback.feedback_type = {param_slot(param_name, 'String')})"
        else:
            # Non-aggregated version for calls_complete
            if self.feedback_type == "*":
                res = inner
            else:
                param_name = pb.add_param(self.feedback_type)
                res = f"if(feedback.feedback_type = {param_slot(param_name, 'String')}, {inner}, NULL)"

        if not self.extra_path:
            return res
        return json_dump_field_as_sql(pb, "feedback", res, self.extra_path, cast)

    def as_select_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        raise NotImplementedError(
            "Feedback fields cannot be selected directly, yet - implement me!"
        )

    def is_heavy(self) -> bool:
        return True

    def supports_aggregation(self) -> bool:
        return True

    def as_sql_without_aggregation(
        self,
        pb: ParamBuilder,
        table_alias: str,
    ) -> str:
        inner = f"feedback.{self.field}"
        if self.feedback_type == "*":
            res = inner
        else:
            param_name = pb.add_param(self.feedback_type)
            res = f"if(feedback.feedback_type = {param_slot(param_name, 'String')}, {inner}, NULL)"

        if not self.extra_path:
            return res
        return json_dump_field_as_sql(pb, "feedback", res, self.extra_path)


class AggregatedDataSizeField(QueryField, BaseModel):
    """Field class for total_storage_size_bytes."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    field: str
    strategy: TableStrategy
    join_table_name: str

    def as_sql(
        self,
        pb: ParamBuilder,
        table_alias: str,
        cast: tsi_query.CastTo | None = None,
        use_agg_fn: bool = True,
    ) -> str:
        base_sql = f"{table_alias}.{self.field}"
        if cast:
            base_sql = clickhouse_cast(base_sql, cast)
        return base_sql

    def as_select_sql(self, pb: ParamBuilder, table_alias: str) -> str:
        if self.strategy.requires_grouping():
            conditional_field = f"""
            CASE
                WHEN any({table_alias}.parent_id) IS NULL
                THEN any({self.join_table_name}.total_storage_size_bytes)
                ELSE NULL
            END
            """
        else:
            conditional_field = f"""
            CASE
                WHEN {table_alias}.parent_id IS NULL
                THEN {self.join_table_name}.total_storage_size_bytes
                ELSE NULL
            END
            """
        return f"{conditional_field} AS {self.field}"

    def is_heavy(self) -> bool:
        return True

    def supports_aggregation(self) -> bool:
        return True

    def as_sql_without_aggregation(
        self,
        pb: ParamBuilder,
        table_alias: str,
    ) -> str:
        return f"{table_alias}.{self.field}"
