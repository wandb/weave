"""Factory for creating field instances from field names and table strategies."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Union

from weave.trace_server.calls_query_builder.fields import (
    AggregatedDataSizeField,
    DynamicField,
    FeedbackField,
    FieldWithTableOverride,
    SimpleField,
    SummaryField,
    STORAGE_SIZE_TABLE_NAME,
    ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME,
)
from weave.trace_server.calls_query_builder.table_strategy import TableStrategy
from weave.trace_server.errors import InvalidFieldError
from weave.trace_server.orm import split_escaped_field_path


# Union type of all concrete field implementations
QueryFieldType = Union[
    SimpleField,
    DynamicField,
    FieldWithTableOverride,
    SummaryField,
    FeedbackField,
    AggregatedDataSizeField,
]


@dataclass
class FieldDefinition:
    """Definition of a field that can be created for any table strategy."""

    field_name: str
    agg_fn: str | None = None
    is_dynamic: bool = False
    table_override: str | None = None
    factory: Callable[[TableStrategy], QueryFieldType] | None = None

    def create(self, strategy: TableStrategy) -> QueryFieldType:
        """Create field instance for given strategy."""
        if self.factory:
            return self.factory(strategy)

        if self.table_override:
            return FieldWithTableOverride(
                field=self.field_name,
                strategy=strategy,
                agg_fn=self.agg_fn,
                table_name=self.table_override,
            )

        if self.is_dynamic:
            return DynamicField(
                field=self.field_name,
                strategy=strategy,
                agg_fn=self.agg_fn,
            )

        return SimpleField(
            field=self.field_name,
            strategy=strategy,
            agg_fn=self.agg_fn,
        )


FIELD_DEFINITIONS = {
    "project_id": FieldDefinition("project_id"),
    "id": FieldDefinition("id"),
    "trace_id": FieldDefinition("trace_id", agg_fn="any"),
    "parent_id": FieldDefinition("parent_id", agg_fn="any"),
    "thread_id": FieldDefinition("thread_id", agg_fn="any"),
    "turn_id": FieldDefinition("turn_id", agg_fn="any"),
    "op_name": FieldDefinition("op_name", agg_fn="any"),
    "started_at": FieldDefinition("started_at", agg_fn="any"),
    "ended_at": FieldDefinition("ended_at", agg_fn="any"),
    "deleted_at": FieldDefinition("deleted_at", agg_fn="any"),
    "exception": FieldDefinition("exception", agg_fn="any"),
    "wb_user_id": FieldDefinition("wb_user_id", agg_fn="any"),
    "wb_run_id": FieldDefinition("wb_run_id", agg_fn="any"),
    "wb_run_step": FieldDefinition("wb_run_step", agg_fn="any"),
    "wb_run_step_end": FieldDefinition("wb_run_step_end", agg_fn="any"),
    "display_name": FieldDefinition("display_name", agg_fn="argMaxMerge"),
    "otel_dump": FieldDefinition("otel_dump", agg_fn="any"),
    "input_refs": FieldDefinition("input_refs", agg_fn="array_concat_agg"),
    "output_refs": FieldDefinition("output_refs", agg_fn="array_concat_agg"),
    # Dynamic fields (JSON navigation)
    "attributes_dump": FieldDefinition(
        "attributes_dump", agg_fn="any", is_dynamic=True
    ),
    "inputs_dump": FieldDefinition("inputs_dump", agg_fn="any", is_dynamic=True),
    "output_dump": FieldDefinition("output_dump", agg_fn="any", is_dynamic=True),
    "summary_dump": FieldDefinition("summary_dump", agg_fn="any", is_dynamic=True),
    # Fields with table overrides
    "storage_size_bytes": FieldDefinition(
        "storage_size_bytes",
        agg_fn="any",
        table_override=STORAGE_SIZE_TABLE_NAME,
    ),
    # Complex fields with custom factories
    "total_storage_size_bytes": FieldDefinition(
        "total_storage_size_bytes",
        factory=lambda strategy: AggregatedDataSizeField(
            field="total_storage_size_bytes",
            strategy=strategy,
            join_table_name=ROLLED_UP_CALL_MERGED_STATS_TABLE_NAME,
        ),
    ),
}


def get_field_by_name_strategy(
    field_name: str, strategy: TableStrategy
) -> QueryFieldType:
    """Get field definition for the given strategy.

    Args:
        field_name: Name of field (e.g., "op_name", "inputs.user_id")
        strategy: Table strategy to create field for

    Returns:
        QueryField instance appropriate for the strategy
    """
    if field_name.startswith("feedback."):
        return FeedbackField.from_path(field_name[len("feedback.") :], strategy)

    if field_name.startswith("summary.weave."):
        summary_field = field_name[len("summary.weave.") :]
        return SummaryField(
            field=field_name,
            strategy=strategy,
            summary_field=summary_field,
        )

    # Check if it's a base field or dynamic path
    field_parts = split_escaped_field_path(field_name)
    start_part = field_parts[0]
    dumped_start_part = start_part + "_dump"

    if dumped_start_part in FIELD_DEFINITIONS:
        definition = FIELD_DEFINITIONS[dumped_start_part]
        field = definition.create(strategy)

        if hasattr(field, "with_path") and len(field_parts) > 1:
            return field.with_path(field_parts[1:])

        return field

    if field_name in FIELD_DEFINITIONS:
        return FIELD_DEFINITIONS[field_name].create(strategy)

    raise InvalidFieldError(f"Field {field_name} is not allowed")
