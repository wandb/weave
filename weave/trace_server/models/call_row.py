"""CallRow dataclass for representing call data in a typed structure.

This module provides a CallRow dataclass that replaces index-based row access
with typed field access, improving code safety and maintainability.
"""

import dataclasses
import datetime
from collections.abc import Iterator
from typing import Any, Optional


@dataclasses.dataclass
class CallRow:
    """Typed representation of a call row with all possible fields.

    This dataclass replaces index-based access (row[call_indices.ended_at])
    with typed field access (call_row.ended_at), making the code more
    maintainable and statically verifiable.

    Attributes:
        project_id: Project identifier
        id: Call identifier
        trace_id: Trace identifier
        parent_id: Parent call identifier (optional)
        thread_id: Thread identifier (optional)
        turn_id: Turn identifier (optional)
        op_name: Operation name
        started_at: When the call started
        ended_at: When the call ended (optional)
        attributes_dump: Serialized attributes JSON
        inputs_dump: Serialized inputs JSON
        output_dump: Serialized output JSON (optional)
        summary_dump: Serialized summary JSON (optional)
        exception: Exception message (optional)
        input_refs: List of input object references
        output_refs: List of output object references
        display_name: Human-readable display name (optional)
        wb_user_id: Weights & Biases user ID (optional)
        wb_run_id: Weights & Biases run ID (optional)
        wb_run_step: Weights & Biases run step (optional)
        wb_run_step_end: Weights & Biases run step end (optional)
        deleted_at: When the call was deleted (optional)
    """

    # Required fields
    project_id: str
    id: str
    trace_id: str
    op_name: str
    started_at: datetime.datetime
    attributes_dump: str
    inputs_dump: str
    input_refs: list[str]
    output_refs: list[str]

    # Optional fields
    parent_id: Optional[str] = None
    thread_id: Optional[str] = None
    turn_id: Optional[str] = None
    ended_at: Optional[datetime.datetime] = None
    output_dump: Optional[str] = None
    summary_dump: Optional[str] = None
    exception: Optional[str] = None
    display_name: Optional[str] = None
    wb_user_id: Optional[str] = None
    wb_run_id: Optional[str] = None
    wb_run_step: Optional[int] = None
    wb_run_step_end: Optional[int] = None
    deleted_at: Optional[datetime.datetime] = None

    def to_clickhouse_row(self) -> list[Any]:
        """Convert CallRow to a list in the exact order ClickHouse expects.

        Returns:
            List of values in ALL_CALL_INSERT_COLUMNS order:
            ['attributes_dump', 'deleted_at', 'display_name', 'ended_at', 'exception',
             'id', 'input_refs', 'inputs_dump', 'op_name', 'output_dump', 'output_refs',
             'parent_id', 'project_id', 'started_at', 'summary_dump', 'thread_id',
             'trace_id', 'turn_id', 'wb_run_id', 'wb_run_step', 'wb_run_step_end', 'wb_user_id']
        """
        return [
            self.attributes_dump,
            self.deleted_at,
            self.display_name,
            self.ended_at,
            self.exception,
            self.id,
            self.input_refs,
            self.inputs_dump,
            self.op_name,
            self.output_dump,
            self.output_refs,
            self.parent_id,
            self.project_id,
            self.started_at,
            self.summary_dump,
            self.thread_id,
            self.trace_id,
            self.turn_id,
            self.wb_run_id,
            self.wb_run_step,
            self.wb_run_step_end,
            self.wb_user_id,
        ]

    def __iter__(self) -> Iterator[Any]:
        """Allow CallRow to be converted to list using list(call_row).

        This maintains backward compatibility with existing code that expects
        list-like behavior.
        """
        return iter(self.to_clickhouse_row())

    @classmethod
    def from_clickhouse_row(cls, row: list[Any]) -> "CallRow":
        """Create CallRow from a ClickHouse row list.

        Args:
            row: List of values in ALL_CALL_INSERT_COLUMNS order

        Returns:
            CallRow instance with fields populated from the row

        Examples:
            >>> row = ["{}", None, "test_call", None, None, "call_123", [], "{}", "op", None, [], None, "proj_456", datetime.now(), None, None, "trace_789", None, None, None, None, None]
            >>> call_row = CallRow.from_clickhouse_row(row)
            >>> call_row.id
            'call_123'
        """
        return cls(
            attributes_dump=row[0],
            deleted_at=row[1],
            display_name=row[2],
            ended_at=row[3],
            exception=row[4],
            id=row[5],
            input_refs=row[6],
            inputs_dump=row[7],
            op_name=row[8],
            output_dump=row[9],
            output_refs=row[10],
            parent_id=row[11],
            project_id=row[12],
            started_at=row[13],
            summary_dump=row[14],
            thread_id=row[15],
            trace_id=row[16],
            turn_id=row[17],
            wb_run_id=row[18],
            wb_run_step=row[19],
            wb_run_step_end=row[20],
            wb_user_id=row[21],
        )

    @classmethod
    def merge_start_and_end(cls, start_call_row: "CallRow", end_call_row: "CallRow") -> "CallRow":
        """Merge start and end CallRows into a complete CallRow.

        This method combines a start CallRow (with start-specific fields) and an end CallRow
        (with end-specific fields) into a single complete CallRow. Start fields are retained,
        and end fields overwrite any corresponding fields in the start CallRow.

        Args:
            start_call_row: CallRow containing start-specific fields
            end_call_row: CallRow containing end-specific fields

        Returns:
            Merged CallRow with all fields from start_call_row and end-specific fields
            from end_call_row

        Examples:
            >>> start = CallRow(project_id="proj", id="call", trace_id="trace",
            ...                 op_name="op", started_at=datetime.now(),
            ...                 attributes_dump="{}", inputs_dump="{}",
            ...                 input_refs=[], output_refs=[])
            >>> end = CallRow(project_id="proj", id="call", trace_id="trace",
            ...               op_name="op", started_at=datetime.now(),
            ...               attributes_dump="{}", inputs_dump="{}",
            ...               input_refs=[], output_refs=[],
            ...               ended_at=datetime.now(), output_dump="{}")
            >>> merged = CallRow.merge_start_and_end(start, end)
            >>> merged.ended_at == end.ended_at
            True
        """
        # Start with a copy of the start_call_row
        merged_data = dataclasses.asdict(start_call_row)

        # Overwrite end-specific fields with values from end_call_row
        end_specific_fields = [
            'ended_at',
            'output_dump',
            'summary_dump',
            'exception',
            'wb_run_step_end'
        ]

        for field in end_specific_fields:
            end_value = getattr(end_call_row, field)
            if end_value is not None:
                merged_data[field] = end_value

        # Create new CallRow with merged data
        return cls(**merged_data)
