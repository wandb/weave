"""File storage operations for the ClickHouse trace server."""
# mypy: disable-error-code="attr-defined"

import ddtrace

from weave.shared.digest import compute_file_digest
from weave.trace_server import clickhouse_trace_server_settings as ch_settings
from weave.trace_server import environment as wf_env
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.clickhouse.utilities import (
    string_to_int_in_range,
)
from weave.trace_server.clickhouse_schema import (
    ALL_FILE_CHUNK_INSERT_COLUMNS,
    FileChunkCreateCHInsertable,
)
from weave.trace_server.datadog import set_root_span_dd_tags
from weave.trace_server.digest_validation import validate_expected_digest
from weave.trace_server.errors import NotFoundError
from weave.trace_server.file_storage import (
    FileStorageClient,
    FileStorageReadError,
    FileStorageWriteError,
    key_for_project_digest,
    read_from_bucket,
    store_in_bucket,
)
from weave.trace_server.file_storage_uris import FileStorageURI
from weave.trace_server.orm import ParamBuilder


class FileOperationsMixin:
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        digest = compute_file_digest(req.content)
        validate_expected_digest(
            expected=req.expected_digest, actual=digest, label="file"
        )

        # During a batch, _file_batch accumulates chunks. If we already have
        # chunks for this (project_id, digest), the content is identical and
        # we can skip the redundant storage I/O (bucket upload or CH insert).
        if any(
            c.project_id == req.project_id and c.digest == digest
            for c in self._file_batch
        ):
            return tsi.FileCreateRes(digest=digest)

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

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._file_create_clickhouse")
    def _file_create_clickhouse(self, req: tsi.FileCreateReq, digest: str) -> None:
        set_root_span_dd_tags({"storage_provider": "clickhouse"})
        chunks = [
            req.content[i : i + ch_settings.FILE_CHUNK_SIZE]
            for i in range(0, len(req.content), ch_settings.FILE_CHUNK_SIZE)
        ]
        self._insert_file_chunks(
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

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._file_create_bucket")
    def _file_create_bucket(
        self,
        req: tsi.FileCreateReq,
        digest: str,
        client: FileStorageClient,
    ) -> None:
        set_root_span_dd_tags({"storage_provider": "bucket"})
        target_file_storage_uri = store_in_bucket(
            client, key_for_project_digest(req.project_id, digest), req.content
        )
        self._insert_file_chunks(
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

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._flush_file_chunks")
    def _flush_file_chunks(self) -> None:
        if not self._flush_immediately:
            raise ValueError("File chunks must be flushed immediately")
        try:
            self._insert_file_chunks(self._file_batch)
        finally:
            self._file_batch = []

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._insert_file_chunks")
    def _insert_file_chunks(
        self, file_chunks: list[FileChunkCreateCHInsertable]
    ) -> None:
        if not self._flush_immediately:
            self._file_batch.extend(file_chunks)
            return

        data = []
        for chunk in file_chunks:
            chunk_dump = chunk.model_dump()
            row = []
            for col in ALL_FILE_CHUNK_INSERT_COLUMNS:
                row.append(chunk_dump.get(col, None))
            data.append(row)

        if data:
            self._insert(
                "files",
                data=data,
                column_names=ALL_FILE_CHUNK_INSERT_COLUMNS,
            )

    def _should_use_file_storage_for_writes(self, project_id: str) -> bool:
        """Determine if we should use file storage for a project."""
        # Check if we should use file storage based on the ramp percentage
        ramp_pct = wf_env.wf_file_storage_project_ramp_pct()
        if ramp_pct is not None:
            # If the hash value is less than the ramp percentage, use file storage
            project_hash_value = string_to_int_in_range(project_id, 100)
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
        # The subquery is responsible for deduplication of file chunks by digest
        query_result = self.ch_client.query(
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
            # The general case where this can occur is when there are multiple
            # writes of the same digest AND the effective `FILE_CHUNK_SIZE`
            # of the most recent write is more than the effective `FILE_CHUNK_SIZE`
            # of any previous write. In that case, you have something like the following:
            # Consider a file of size 500 bytes.
            # Insert Batch 1 (chunk_size=100): C0(0-99), C1(100-199), C2(200-299), C3(300-399), C4(400-499)
            # Insert Batch 2 (chunk_size=50): C0(0-49), C1(50-99), C2(100-149), C3(150-199), C4(200-249), C5(250-299), C6(300-349), C7(350-399), C8(400-449), C9(450-499)
            # Insert Batch 3 (chunk_size=200): C0(0-199), C1(200-399), C2(400-499)
            #
            # When Clickhouse runs it's merge operation, it keeps the last inserted rows according to the index (project, digest, chunk_index).
            # Similarly, the inner select statement in the query above (partitioned and keep row 1) does the same thing.
            #
            # As a result, the resulting query gives you all the chunks from batch 3, then any "extra" chunks from previous batches.
            # |--------- Insert Batch 3 --------| |-------------------------- Extra Chunks from Batch 2 -----------------------------------|
            # C0(0-199), C1(200-399), C2(400-499), C3(150-199), C4(200-249), C5(250-299), C6(300-349), C7(350-399), C8(400-449), C9(450-499)
            #
            #
            # Those "extra" chunks are no long valid, but will be returned by the query. By design, we include the expected number of chunks in the response
            # and since the last insert batch is the valid one, we can truncate the response to the expected number of chunks to isolate the valid chunks.
            #
            #
            # Now, practically, we have never changed the `FILE_CHUNK_SIZE` - nor should we!
            # However, with bucket storage, we don't chunk at all - storing the data effectively as a single chunk.
            # This effectively means that `FILE_CHUNK_SIZE` for these cases is the size of the file!. Therefore,
            # in such cases where a file was written before bucket storage (using chunking) and then after, we will
            # reach a situation that matches the general case above.
            #
            # To solve this, we truncate the response to the expected number of chunks to isolate the valid chunks.
            result_rows = result_rows[:n_chunks]

        # There are 2 cases:
        # 1: file_storage_uri_str is not none (storing in file store)
        # 2: file_storage_uri_str is None (storing directly in clickhouse)
        bytes = b""

        for result_row in result_rows:
            chunk_file_storage_uri_str = result_row[2]
            if chunk_file_storage_uri_str:
                file_storage_uri = FileStorageURI.parse_uri_str(
                    chunk_file_storage_uri_str
                )
                bytes += self._file_read_bucket(file_storage_uri)
            else:
                chunk_bytes = result_row[1]
                bytes += chunk_bytes
                set_root_span_dd_tags({"storage_provider": "clickhouse"})

        set_root_span_dd_tags({"read_bytes": len(bytes)})
        return tsi.FileContentReadRes(content=bytes)

    @ddtrace.tracer.wrap(name="clickhouse_trace_server_batched._file_read_bucket")
    def _file_read_bucket(self, file_storage_uri: FileStorageURI) -> bytes:
        set_root_span_dd_tags({"storage_provider": "bucket"})
        client = self.file_storage_client
        if client is None:
            raise FileStorageReadError("File storage client is not configured")
        return read_from_bucket(client, file_storage_uri)

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        pb = ParamBuilder()

        project_id_param = pb.add_param(req.project_id)

        query = f"""
        SELECT sum(size_bytes) as total_size_bytes
        FROM files_stats
        WHERE project_id = {{{project_id_param}: String}}
        """
        result = self.ch_client.query(query, parameters=pb.get_params())

        if len(result.result_rows) == 0 or result.result_rows[0][0] is None:
            raise RuntimeError("No results found")

        return tsi.FilesStatsRes(total_size_bytes=result.result_rows[0][0])
