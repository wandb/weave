"""Table upload chunking functionality for efficient parallel table creation."""

import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, TypeVar

from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)

# Constants for table chunking
TARGET_CHUNK_BYTES = 10 * 1024 * 1024  # 10MB
MAX_CONCURRENT_CHUNKS = 32
RowItemType = TypeVar("RowItemType")


class TableChunkManager:
    """Manages concurrent creation of table chunks with proper error handling."""

    def __init__(
        self,
        max_workers: int = MAX_CONCURRENT_CHUNKS,
        target_chunk_bytes: int = TARGET_CHUNK_BYTES,
    ):
        self.max_workers = max_workers
        self.target_chunk_bytes = target_chunk_bytes

    def calculate_request_bytes(self, req: Any) -> int:
        """Calculate the estimated size in bytes of a request."""
        return len(req.model_dump_json(by_alias=True).encode("utf-8"))

    def calculate_row_bytes(self, row: RowItemType) -> int:
        """Calculate the size in bytes of a single row."""
        return len(str(row).encode("utf-8"))

    def create_chunks(self, rows: list[RowItemType]) -> list[list[RowItemType]]:
        """
        Split rows into chunks based on target byte size.

        Args:
            rows: List of rows to chunk

        Returns:
            List of row chunks
        """
        chunks = []
        current_chunk: list[RowItemType] = []
        current_chunk_bytes = 0

        for row in rows:
            row_bytes = self.calculate_row_bytes(row)

            if (
                current_chunk_bytes + row_bytes > self.target_chunk_bytes
                and current_chunk
            ):
                chunks.append(current_chunk)
                current_chunk = [row]
                current_chunk_bytes = row_bytes
            else:
                current_chunk.append(row)
                current_chunk_bytes += row_bytes

        if current_chunk:
            chunks.append(current_chunk)

        chunks = [chunk for chunk in chunks if chunk]
        if not chunks:
            chunks = [rows]

        return chunks

    def process_chunks_concurrently(
        self,
        chunks: list[list[RowItemType]],
        create_chunk_fn: Callable[[str, list[RowItemType], int], tsi.TableCreateRes],
        project_id: str,
    ) -> tuple[list[str], list[str]]:
        """
        Process chunks concurrently while preserving order.

        Args:
            chunks: List of row chunks
            create_chunk_fn: Function to create a single chunk
            project_id: Project ID for the chunks

        Returns:
            Tuple of (table_digests, all_row_digests)
        """
        with ThreadPoolExecutor(
            max_workers=min(len(chunks), self.max_workers)
        ) as executor:
            futures = []
            for i, chunk in enumerate(chunks):
                future = executor.submit(create_chunk_fn, project_id, chunk, i)
                futures.append((i, future))

            table_digests: list[str] = [""] * len(chunks)
            all_row_digests: list[str] = []

            for chunk_index, future in futures:
                try:
                    result = future.result()
                    table_digests[chunk_index] = result.digest
                    all_row_digests.extend(result.row_digests)
                except Exception:
                    logger.exception(f"Failed to create table chunk {chunk_index}")
                    raise

            assert all(digest for digest in table_digests), (
                "Not all table chunks were created successfully"
            )

            return table_digests, all_row_digests
