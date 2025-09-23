"""Table upload chunking functionality for efficient parallel table creation."""

import dataclasses
import logging
from collections.abc import Sequence
from typing import Any, TypeVar

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
        return len(str(row).encode("utf-8"))

    def create_chunks(self, rows: Sequence[RowItemType]) -> list[list[RowItemType]]:
        """Split rows into chunks based on target byte size.

        Args:
            rows: List of rows to chunk

        Returns:
            List of row chunks
        """
        if not rows:
            return []

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
