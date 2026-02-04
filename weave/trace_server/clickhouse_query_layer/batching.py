# ClickHouse Batching - Batch management and flushing logic

import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import ddtrace

from weave.trace_server import environment as wf_env
from weave.trace_server.clickhouse_query_layer import settings as ch_settings
from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient, num_bytes
from weave.trace_server.clickhouse_query_layer.schema import (
    ALL_CALL_COMPLETE_INSERT_COLUMNS,
    ALL_CALL_INSERT_COLUMNS,
    ALL_CALL_JSON_COLUMNS,
    ALL_FILE_CHUNK_INSERT_COLUMNS,
    FileChunkCreateCHInsertable,
)
from weave.trace_server.datadog import set_current_span_dd_tags
from weave.trace_server.errors import InsertTooLarge

if TYPE_CHECKING:
    from weave.trace_server.kafka import KafkaProducer

logger = logging.getLogger(__name__)


class BatchManager:
    """Manages batching for ClickHouse inserts.

    This class handles thread-local batch state for calls, files, and calls_complete,
    as well as flushing logic for efficient bulk inserts.
    """

    def __init__(
        self,
        ch_client: ClickHouseClient,
        kafka_producer_getter: Callable[[], "KafkaProducer"],
    ):
        self._ch_client = ch_client
        self._thread_local = threading.local()
        self._kafka_producer_getter = kafka_producer_getter

    @property
    def _flush_immediately(self) -> bool:
        return getattr(self._thread_local, "flush_immediately", True)

    @_flush_immediately.setter
    def _flush_immediately(self, value: bool) -> None:
        self._thread_local.flush_immediately = value

    @property
    def _call_batch(self) -> list[list[Any]]:
        if not hasattr(self._thread_local, "call_batch"):
            self._thread_local.call_batch = []
        return self._thread_local.call_batch

    @_call_batch.setter
    def _call_batch(self, value: list[list[Any]]) -> None:
        self._thread_local.call_batch = value

    @property
    def _file_batch(self) -> list[FileChunkCreateCHInsertable]:
        if not hasattr(self._thread_local, "file_batch"):
            self._thread_local.file_batch = []
        return self._thread_local.file_batch

    @_file_batch.setter
    def _file_batch(self, value: list[FileChunkCreateCHInsertable]) -> None:
        self._thread_local.file_batch = value

    @property
    def _calls_complete_batch(self) -> list[list[Any]]:
        if not hasattr(self._thread_local, "calls_complete_batch"):
            self._thread_local.calls_complete_batch = []
        return self._thread_local.calls_complete_batch

    @_calls_complete_batch.setter
    def _calls_complete_batch(self, value: list[list[Any]]) -> None:
        self._thread_local.calls_complete_batch = value

    @contextmanager
    def call_batch(self) -> Iterator[None]:
        """Context manager for batching multiple call operations.

        Not thread safe - do not use across threads.
        """
        self._flush_immediately = False
        try:
            yield
            self._flush_immediately = True
            self.flush_file_chunks()
            self.flush_calls()
            self.flush_calls_complete()
            # Flush kafka producer if online eval is enabled
            if wf_env.wf_enable_online_eval():
                self._kafka_producer_getter().flush()
        finally:
            self._file_batch = []
            self._call_batch = []
            self._calls_complete_batch = []
            self._flush_immediately = True

    # =========================================================================
    # Call Batch Operations
    # =========================================================================

    def add_call_to_batch(self, row: list[Any]) -> None:
        """Add a call row to the batch."""
        self._call_batch.append(row)
        if self._flush_immediately:
            self.flush_calls()

    @ddtrace.tracer.wrap(name="batch_manager.insert_call_batch")
    def insert_call_batch(
        self,
        batch: list,
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,
    ) -> None:
        """Insert a batch of calls into the call_parts table."""
        set_current_span_dd_tags(
            {"batch_manager.insert_call_batch.count": str(len(batch))}
        )
        if not batch:
            return

        self._ch_client.insert(
            "call_parts",
            data=batch,
            column_names=ALL_CALL_INSERT_COLUMNS,
            settings=settings,
            do_sync_insert=do_sync_insert,
        )

    @ddtrace.tracer.wrap(name="batch_manager.flush_calls")
    def flush_calls(self) -> None:
        """Flush the call batch to the database."""
        try:
            self.insert_call_batch(self._call_batch)
        except InsertTooLarge:
            logger.info("Retrying with large objects stripped.")
            batch = self._strip_large_values(self._call_batch)
            # Insert rows one at a time after stripping large values
            for row in batch:
                self.insert_call_batch([row])
        finally:
            self._call_batch = []

    # =========================================================================
    # Calls Complete Batch Operations
    # =========================================================================

    def add_call_complete_to_batch(self, row: list[Any]) -> None:
        """Add a calls_complete row to the batch."""
        self._calls_complete_batch.append(row)
        if self._flush_immediately:
            self.flush_calls_complete()

    @ddtrace.tracer.wrap(name="batch_manager.insert_call_complete_batch")
    def insert_call_complete_batch(
        self,
        batch: list,
        settings: dict[str, Any] | None = None,
        do_sync_insert: bool = False,
    ) -> None:
        """Insert a batch of complete calls into the calls_complete table."""
        set_current_span_dd_tags(
            {"batch_manager.insert_call_complete_batch.count": str(len(batch))}
        )
        if not batch:
            return

        self._ch_client.insert(
            "calls_complete",
            data=batch,
            column_names=ALL_CALL_COMPLETE_INSERT_COLUMNS,
            settings=settings,
            do_sync_insert=do_sync_insert,
        )

    @ddtrace.tracer.wrap(name="batch_manager.flush_calls_complete")
    def flush_calls_complete(self) -> None:
        """Flush the calls_complete batch to the database."""
        if not self._calls_complete_batch:
            return

        try:
            self.insert_call_complete_batch(self._calls_complete_batch)
        except InsertTooLarge:
            # Try 1 by 1
            for row in self._calls_complete_batch:
                self.insert_call_complete_batch([row])
        finally:
            self._calls_complete_batch = []

    # =========================================================================
    # File Batch Operations
    # =========================================================================

    def add_file_chunks_to_batch(
        self, file_chunks: list[FileChunkCreateCHInsertable]
    ) -> None:
        """Add file chunks to the batch."""
        if not self._flush_immediately:
            self._file_batch.extend(file_chunks)
            return
        self._insert_file_chunks(file_chunks)

    @ddtrace.tracer.wrap(name="batch_manager.flush_file_chunks")
    def flush_file_chunks(self) -> None:
        """Flush the file batch to the database."""
        if not self._flush_immediately:
            raise ValueError("File chunks must be flushed immediately")
        try:
            self._insert_file_chunks(self._file_batch)
        finally:
            self._file_batch = []

    @ddtrace.tracer.wrap(name="batch_manager.insert_file_chunks")
    def _insert_file_chunks(
        self, file_chunks: list[FileChunkCreateCHInsertable]
    ) -> None:
        """Insert file chunks into the files table."""
        data = []
        for chunk in file_chunks:
            chunk_dump = chunk.model_dump()
            row = []
            for col in ALL_FILE_CHUNK_INSERT_COLUMNS:
                row.append(chunk_dump.get(col, None))
            data.append(row)

        if data:
            self._ch_client.insert(
                "files",
                data=data,
                column_names=ALL_FILE_CHUNK_INSERT_COLUMNS,
            )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    @ddtrace.tracer.wrap(name="batch_manager.analyze_call_batch_breakdown")
    def analyze_call_batch_breakdown(self) -> None:
        """Analyze the batch to count calls with starts but no ends."""
        if not self._call_batch:
            return

        try:
            id_idx = ALL_CALL_INSERT_COLUMNS.index("id")
            started_at_idx = ALL_CALL_INSERT_COLUMNS.index("started_at")
            ended_at_idx = ALL_CALL_INSERT_COLUMNS.index("ended_at")

            started_call_ids: set[str] = set()
            ended_call_ids: set[str] = set()

            for row in self._call_batch:
                call_id = row[id_idx]
                started_at = row[started_at_idx]
                ended_at = row[ended_at_idx]

                if started_at is not None:
                    started_call_ids.add(call_id)
                if ended_at is not None:
                    ended_call_ids.add(call_id)

            unmatched_starts = started_call_ids - ended_call_ids

            set_current_span_dd_tags(
                {
                    "batch_manager.flush_calls.unmatched_starts": len(unmatched_starts),
                }
            )
        except Exception:
            # Under no circumstances should we block ingest with an error
            pass

    @ddtrace.tracer.wrap(name="batch_manager.strip_large_values")
    def _strip_large_values(self, batch: list[list[Any]]) -> list[list[Any]]:
        """Iterate through the batch and replace large JSON values with placeholders.

        Only considers JSON dump columns and ensures their combined size stays under
        the limit by selectively replacing the largest values.
        """
        stripped_count = 0
        final_batch = []

        json_column_indices = [
            ALL_CALL_INSERT_COLUMNS.index(f"{col}_dump")
            for col in ALL_CALL_JSON_COLUMNS
        ]
        entity_too_large_payload_byte_size = num_bytes(
            ch_settings.ENTITY_TOO_LARGE_PAYLOAD
        )

        for item in batch:
            # Calculate only JSON dump bytes
            json_idx_size_pairs = [(i, num_bytes(item[i])) for i in json_column_indices]
            total_json_bytes = sum(size for _, size in json_idx_size_pairs)

            # If over limit, try to optimize by selectively stripping largest JSON values
            stripped_item = list(item)
            sorted_json_idx_size_pairs = sorted(
                json_idx_size_pairs, key=lambda x: x[1], reverse=True
            )

            # Try to get under the limit by replacing largest JSON values
            for col_idx, size in sorted_json_idx_size_pairs:
                if (
                    total_json_bytes
                    <= ch_settings.CLICKHOUSE_SINGLE_ROW_INSERT_BYTES_LIMIT
                ):
                    break

                # Replace this large JSON value with placeholder, update running size
                stripped_item[col_idx] = ch_settings.ENTITY_TOO_LARGE_PAYLOAD
                total_json_bytes -= size - entity_too_large_payload_byte_size
                stripped_count += 1

            final_batch.append(stripped_item)

        ddtrace.tracer.current_span().set_tags(
            {"batch_manager.strip_large_values.stripped_count": str(stripped_count)}
        )
        return final_batch
