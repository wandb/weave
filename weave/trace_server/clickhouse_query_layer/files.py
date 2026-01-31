# ClickHouse Files - File storage operations

import hashlib
import logging
from typing import TYPE_CHECKING

import ddtrace

from weave.trace_server.clickhouse_query_layer import settings as ch_settings
from weave.trace_server import environment as wf_env
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse_query_layer.batching import BatchManager
from weave.trace_server.clickhouse_query_layer.client import ClickHouseClient
from weave.trace_server.clickhouse_schema import FileChunkCreateCHInsertable
from weave.trace_server.datadog import set_root_span_dd_tags
from weave.trace_server.errors import NotFoundError
from weave.trace_server.file_storage import (
    FileStorageClient,
    FileStorageReadError,
    FileStorageWriteError,
    key_for_project_digest,
    maybe_get_storage_client_from_env,
    read_from_bucket,
    store_in_bucket,
)
from weave.trace_server.file_storage_uris import FileStorageURI
from weave.trace_server.trace_server_interface_util import bytes_digest

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class FilesRepository:
    """Repository for file storage operations."""

    def __init__(
        self,
        ch_client: ClickHouseClient,
        batch_manager: BatchManager,
    ):
        self._ch_client = ch_client
        self._batch_manager = batch_manager
        self._file_storage_client: FileStorageClient | None = None

    @property
    def file_storage_client(self) -> FileStorageClient | None:
        """Get or create the file storage client."""
        if self._file_storage_client is not None:
            return self._file_storage_client
        self._file_storage_client = maybe_get_storage_client_from_env()
        return self._file_storage_client

    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        """Create a file, storing in bucket or ClickHouse based on config."""
        digest = bytes_digest(req.content)
        use_file_storage = self._should_use_file_storage_for_writes(req.project_id)
        client = self.file_storage_client

        if client is not None and use_file_storage:
            try:
                self._file_create_bucket(req, digest, client)
            except FileStorageWriteError:
                self._file_create_clickhouse(req, digest)
        else:
            self._file_create_clickhouse(req, digest)
        set_root_span_dd_tags({"write_bytes": len(req.content)})
        return tsi.FileCreateRes(digest=digest)

    @ddtrace.tracer.wrap(name="files_repository._file_create_clickhouse")
    def _file_create_clickhouse(self, req: tsi.FileCreateReq, digest: str) -> None:
        """Create a file in ClickHouse (chunked storage)."""
        set_root_span_dd_tags({"storage_provider": "clickhouse"})
        chunks = [
            req.content[i : i + ch_settings.FILE_CHUNK_SIZE]
            for i in range(0, len(req.content), ch_settings.FILE_CHUNK_SIZE)
        ]
        self._batch_manager.add_file_chunks_to_batch(
            [
                FileChunkCreateCHInsertable(
                    project_id=req.project_id,
                    digest=digest,
                    chunk_index=i,
                    n_chunks=len(chunks),
                    name=req.name,
                    val_bytes=chunk,
                    bytes_stored=len(chunk),
                    file_storage_uri=None,
                )
                for i, chunk in enumerate(chunks)
            ]
        )

    @ddtrace.tracer.wrap(name="files_repository._file_create_bucket")
    def _file_create_bucket(
        self, req: tsi.FileCreateReq, digest: str, client: FileStorageClient
    ) -> None:
        """Create a file in bucket storage."""
        set_root_span_dd_tags({"storage_provider": "bucket"})
        target_file_storage_uri = store_in_bucket(
            client, key_for_project_digest(req.project_id, digest), req.content
        )
        self._batch_manager.add_file_chunks_to_batch(
            [
                FileChunkCreateCHInsertable(
                    project_id=req.project_id,
                    digest=digest,
                    chunk_index=0,
                    n_chunks=1,
                    name=req.name,
                    val_bytes=b"",
                    bytes_stored=len(req.content),
                    file_storage_uri=target_file_storage_uri.to_uri_str(),
                )
            ]
        )

    def _should_use_file_storage_for_writes(self, project_id: str) -> bool:
        """Determine if we should use file storage for a project."""
        # Check if we should use file storage based on the ramp percentage
        ramp_pct = wf_env.wf_file_storage_project_ramp_pct()
        if ramp_pct is not None:
            project_hash_value = _string_to_int_in_range(project_id, 100)
            if project_hash_value < ramp_pct:
                return True

        # Check if we should use file storage based on the allow list
        project_allow_list = wf_env.wf_file_storage_project_allow_list()
        if project_allow_list is None:
            return False

        universally_enabled = (
            len(project_allow_list) == 1 and project_allow_list[0] == "*"
        )

        if not universally_enabled and project_id not in project_allow_list:
            return False

        return True

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        """Read file content from storage."""
        query_result = self._ch_client.ch_client.query(
            """
            SELECT n_chunks, val_bytes, file_storage_uri
            FROM (
                SELECT *
                FROM (
                        SELECT *,
                            row_number() OVER (PARTITION BY project_id, digest, chunk_index) AS rn
                        FROM files
                        WHERE project_id = {project_id:String} AND digest = {digest:String}
                    )
                WHERE rn = 1
                ORDER BY project_id, digest, chunk_index
            )
            WHERE project_id = {project_id:String} AND digest = {digest:String}""",
            parameters={"project_id": req.project_id, "digest": req.digest},
            column_formats={"val_bytes": "bytes"},
        )

        if len(query_result.result_rows) == 0:
            raise NotFoundError(f"File with digest {req.digest} not found")

        n_chunks = query_result.result_rows[0][0]
        result_rows = list(query_result.result_rows)

        if len(result_rows) < n_chunks:
            raise ValueError("Missing chunks")
        elif len(result_rows) > n_chunks:
            # Truncate to expected number of chunks (handles chunk size changes)
            result_rows = result_rows[:n_chunks]

        content = b""

        for result_row in result_rows:
            chunk_file_storage_uri_str = result_row[2]
            if chunk_file_storage_uri_str:
                file_storage_uri = FileStorageURI.parse_uri_str(
                    chunk_file_storage_uri_str
                )
                content += self._file_read_bucket(file_storage_uri)
            else:
                chunk_bytes = result_row[1]
                content += chunk_bytes
                set_root_span_dd_tags({"storage_provider": "clickhouse"})

        set_root_span_dd_tags({"read_bytes": len(content)})
        return tsi.FileContentReadRes(content=content)

    @ddtrace.tracer.wrap(name="files_repository._file_read_bucket")
    def _file_read_bucket(self, file_storage_uri: FileStorageURI) -> bytes:
        """Read file content from bucket storage."""
        set_root_span_dd_tags({"storage_provider": "bucket"})
        client = self.file_storage_client
        if client is None:
            raise FileStorageReadError("File storage client is not configured")
        return read_from_bucket(client, file_storage_uri)


def _string_to_int_in_range(input_string: str, range_max: int) -> int:
    """Convert a string to a deterministic integer within a specified range.

    Args:
        input_string: The string to convert to an integer.
        range_max: The maximum allowed value (exclusive).

    Returns:
        int: A deterministic integer value between 0 and range_max.
    """
    hash_obj = hashlib.md5(input_string.encode())
    hash_int = int(hash_obj.hexdigest(), 16)
    return hash_int % range_max
