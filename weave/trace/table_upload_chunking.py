"""Table upload chunking functionality for efficient parallel table creation."""

import dataclasses
import logging
from collections.abc import Sequence
from typing import Any, TypeVar

from weave.trace.settings import should_use_binary_table_upload

logger = logging.getLogger(__name__)

# Constants for table chunking
TARGET_CHUNK_BYTES = 10 * 1024 * 1024  # 10MB
RowItemType = TypeVar("RowItemType")


@dataclasses.dataclass
class ChunkingConfig:
    """Configuration for table chunking behavior."""

    use_chunking: bool
    use_parallel_chunks: bool


class TableChunkManager:
    """Manages concurrent creation of table chunks with proper error handling."""

    def __init__(self, target_chunk_bytes: int = TARGET_CHUNK_BYTES):
        self.target_chunk_bytes = target_chunk_bytes

    def calculate_request_bytes(self, req: Any) -> int:
        """Calculate the estimated size in bytes of a request."""
        return len(req.model_dump_json(by_alias=True).encode("utf-8"))

    def calculate_row_bytes(self, row: object) -> int:
        """Calculate the size in bytes of a single row."""
        use_compression = should_use_binary_table_upload()
        if use_compression:
            return len(str(row).encode("utf-8")) // 10
        return len(str(row).encode("utf-8"))

    def create_chunks(self, rows: Sequence[RowItemType]) -> list[list[RowItemType]]:
        """
        Split rows into chunks based on target byte size.

        Uses sampling for large datasets to improve performance.

        Args:
            rows: List of rows to chunk

        Returns:
            List of row chunks
        """
        if not rows:
            return []

        total_rows = len(rows)

        # For small datasets, use exact calculation
        if total_rows <= 100:
            return self._create_chunks_exact(rows)

        # For large datasets, estimate average row size using sampling
        # Sample size is min(100, 10% of rows) to get a good estimate
        sample_size = min(100, max(10, total_rows // 10))
        sample_step = total_rows // sample_size

        # Calculate sample bytes
        sample_total_bytes = 0
        for i in range(0, total_rows, sample_step):
            if i < total_rows:
                sample_total_bytes += self.calculate_row_bytes(rows[i])

        avg_row_bytes = sample_total_bytes / sample_size

        # Add 10% buffer to account for variance
        avg_row_bytes = int(avg_row_bytes * 1.1)

        # Calculate approximate rows per chunk
        rows_per_chunk = max(1, int(self.target_chunk_bytes / avg_row_bytes))

        # Create chunks
        chunks = []
        for i in range(0, total_rows, rows_per_chunk):
            chunk = list(rows[i : i + rows_per_chunk])
            chunks.append(chunk)

        return chunks

    def _create_chunks_exact(
        self, rows: Sequence[RowItemType]
    ) -> list[list[RowItemType]]:
        """Create chunks using exact byte calculation for small datasets."""
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

        return chunks
