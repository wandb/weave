from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Any, Callable, TypedDict, TypeVar

import diskcache
from pydantic import BaseModel
from typing_extensions import Self

from weave.trace.refs import ObjectRef, parse_uri
from weave.trace.settings import (
    server_cache_dir,
    server_cache_size_limit,
    use_server_cache,
)
from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)

TReq = TypeVar("TReq", bound=BaseModel)
TRes = TypeVar("TRes", bound=BaseModel)


class CacheRecorder(TypedDict):
    hits: int
    misses: int
    errors: int
    skips: int


def digest_is_cacheable(digest: str) -> bool:
    """
    Check if a digest is cachable.

    Examples:
    - v1 -> False
    - oioZ7zgsCq4K7tfFQZRubx3ZGPXmFyaeoeWHHd8KUl8 -> True
    """
    # If it looks like a version, it is not cachable
    if digest.startswith("v"):
        try:
            int(digest[1:])
        except ValueError:
            return True
        return False
    elif digest == "latest":
        return False

    return True


class CachingMiddlewareTraceServer(tsi.TraceServerInterface):
    """A middleware trace server that provides caching functionality.

    This server wraps another trace server and caches responses to improve performance.
    It uses diskcache to store responses on disk and implements caching for read-only
    operations like obj_read, table_query, etc.

    Attributes:
        _next_trace_server: The underlying trace server being wrapped
        _cache: The disk cache instance used to store responses
        _cache_recorder: Metrics tracking cache hits, misses, errors and skips
    """

    _next_trace_server: tsi.TraceServerInterface
    _cache_prefix: str

    def __init__(
        self,
        next_trace_server: tsi.TraceServerInterface,
        cache_dir: str | None = None,
        size_limit: int = 1_000_000_000,
    ):
        """Initialize the caching middleware.

        Args:
            next_trace_server: The trace server to wrap with caching
            cache_dir: Directory to store the disk cache. If None, uses system temp dir
            size_limit: Maximum size in bytes for the cache (default 1GB)
        """
        self._next_trace_server = next_trace_server
        self._cache: diskcache.Cache[str, str | bytes] = diskcache.Cache(
            cache_dir, size_limit=size_limit
        )
        self._cache_recorder: CacheRecorder = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "skips": 0,
        }

    def __del__(self) -> None:
        """Cleanup method called when object is destroyed."""
        try:
            self._cache.close()
        except Exception as e:
            logger.exception(f"Error closing cache: {e}")

    @classmethod
    def from_env(cls, next_trace_server: tsi.TraceServerInterface) -> Self:
        cache_dir = server_cache_dir()
        size_limit = server_cache_size_limit()
        return cls(next_trace_server, cache_dir, size_limit)

    def _safe_cache_get(self, key: str) -> Any:
        """Safely retrieve a value from cache, handling errors and recording metrics.

        Args:
            key: The cache key to look up

        Returns:
            The cached value if found, None otherwise
        """
        if not use_server_cache():
            self._cache_recorder["skips"] += 1
            return None

        try:
            res = self._cache.get(key)
        except Exception as e:
            logger.exception(f"Error getting cached value: {e}")
            self._cache_recorder["errors"] += 1
            return None
        if res is not None:
            self._cache_recorder["hits"] += 1
        else:
            self._cache_recorder["misses"] += 1
        return res

    def _safe_cache_set(self, key: str, value: Any) -> None:
        """Safely store a value in cache, handling errors.

        Args:
            key: The cache key
            value: The value to cache
        """
        if not use_server_cache():
            return None
        try:
            self._cache.set(key, value)
        except Exception as e:
            logger.exception(f"Error caching value: {e}")
        return None

    def _safe_cache_delete(self, key: str) -> None:
        if not use_server_cache():
            return None
        try:
            self._cache.delete(key)
        except Exception as e:
            logger.exception(f"Error deleting cached value: {e}")
        return None

    def _safe_cache_delete_prefix(self, prefix: str) -> None:
        if not use_server_cache():
            return None
        try:
            for key in self._cache:
                if key.startswith(prefix):
                    self._safe_cache_delete(key)
        except Exception as e:
            logger.exception(f"Error deleting cached values with prefix: {e}")

    def _with_cache(
        self,
        func: Callable[[TReq], TRes],
        req: TReq,
        namespace: str,
        make_cache_key: Callable[[TReq], str],
        serialize: Callable[[TRes], str | bytes],
        deserialize: Callable[[str | bytes], TRes],
    ) -> TRes:
        """Cache the result of a function call using the provided serialization methods.

        This is the core caching implementation that handles serialization/deserialization
        of cached values and error handling.

        Args:
            namespace: Namespace to prefix the cache key with
            make_cache_key: Function to generate a cache key from the request
            func: The function to cache results for
            req: The request object
            serialize: Function to serialize the response to a string/bytes
            deserialize: Function to deserialize the cached value back to a response

        Returns:
            The function result, either from cache or from calling func
        """
        try:
            cache_key = f"{namespace}_{make_cache_key(req)}"
        except Exception as e:
            logger.exception(f"Error creating cache key: {e}")
            return func(req)
        try:
            cached_json_value = self._safe_cache_get(cache_key)
            if cached_json_value:
                return deserialize(cached_json_value)
        except Exception as e:
            logger.exception(f"Error validating cached value: {e}")
            self._safe_cache_delete(cache_key)
        res = func(req)
        try:
            json_value_to_cache = serialize(res)
            self._safe_cache_set(cache_key, json_value_to_cache)
        except Exception as e:
            logger.exception(f"Error caching value: {e}")
        return res

    def _with_cache_pydantic(
        self,
        func: Callable[[TReq], TRes],
        req: TReq,
        res_type: type[TRes],
    ) -> TRes:
        """Cache the result of a function that takes and returns Pydantic models.

        This is a convenience wrapper around _with_cache that handles Pydantic model
        serialization automatically.

        Args:
            func: The function to cache results for
            req: The request object (must be a Pydantic model)
            res_type: The response type (must be a Pydantic model)

        Returns:
            The function result, either from cache or from calling func
        """
        return self._with_cache(
            func,
            req,
            func.__name__,
            lambda req: req.model_dump_json(),
            lambda res: res.model_dump_json(),
            lambda json_value: res_type.model_validate_json(json_value),
        )

    def reset_cache_recorder(self) -> None:
        self._cache_recorder = {
            "hits": 0,
            "misses": 0,
            "errors": 0,
            "skips": 0,
        }

    def get_cache_recorder(self) -> CacheRecorder:
        return self._cache_recorder.copy()

    # Cacheable Methods:
    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        if not digest_is_cacheable(req.digest):
            return self._next_trace_server.obj_read(req)
        return self._with_cache_pydantic(
            self._next_trace_server.obj_read, req, tsi.ObjReadRes
        )

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        if req.digests:
            for digest in req.digests:
                try:
                    cache_key_prefix = f'obj_read_{{"project_id":"{req.project_id}","object_id":"{req.object_id}","digest":"{digest}"'
                    self._safe_cache_delete_prefix(cache_key_prefix)
                except Exception as e:
                    logger.exception(f"Error deleting cached value: {e}")
        else:
            cache_key_prefix = f'obj_read_{{"project_id":"{req.project_id}","object_id":"{req.object_id}"'
            self._safe_cache_delete_prefix(cache_key_prefix)
        return self._next_trace_server.obj_delete(req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        if not digest_is_cacheable(req.digest):
            return self._next_trace_server.table_query(req)
        return self._with_cache_pydantic(
            self._next_trace_server.table_query, req, tsi.TableQueryRes
        )

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        # I am not sure the best way to cache the iterator here. TODO
        return self._next_trace_server.table_query_stream(req)

    # This is a legacy endpoint, it should be removed once the client is mostly updated
    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        if not digest_is_cacheable(req.digest):
            return self._next_trace_server.table_query_stats(req)
        return self._with_cache_pydantic(
            self._next_trace_server.table_query_stats, req, tsi.TableQueryStatsRes
        )

    def table_query_stats_batch(
        self, req: tsi.TableQueryStatsBatchReq
    ) -> tsi.TableQueryStatsBatchRes:
        if any(not digest_is_cacheable(digest) for digest in req.digests or []):
            return self._next_trace_server.table_query_stats_batch(req)
        return self._with_cache_pydantic(
            self._next_trace_server.table_query_stats_batch,
            req,
            tsi.TableQueryStatsBatchRes,
        )

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        """Read multiple refs, utilizing cache for individual refs.

        This method implements special caching logic to:
        1. Check cache for each individual ref
        2. Only query the underlying server for refs not in cache
        3. Cache newly retrieved refs
        4. Combine cached and new results

        Args:
            req: Request containing list of refs to read

        Returns:
            Response containing values for all requested refs
        """
        final_results = [None] * len(req.refs)
        needed_refs: list[str] = []
        needed_indices: list[int] = []

        for i, ref in enumerate(req.refs):
            existing_result = None
            try:
                existing_result = self._safe_cache_get(ref)
            except Exception as e:
                logger.exception(f"Error getting cached value: {e}")
            if existing_result:
                final_results[i] = existing_result
            else:
                needed_refs.append(ref)
                needed_indices.append(i)

        if needed_refs:
            new_req = tsi.RefsReadBatchReq(refs=needed_refs)
            needed_results = self._next_trace_server.refs_read_batch(new_req)
            for i, val in zip(needed_indices, needed_results.vals):
                final_results[i] = val
                try:
                    parsed_ref = parse_uri(ref)
                    if isinstance(parsed_ref, ObjectRef) and digest_is_cacheable(
                        parsed_ref.digest
                    ):
                        self._safe_cache_set(ref, val)
                except Exception as e:
                    logger.exception(f"Error caching values: {e}")

        return tsi.RefsReadBatchRes(vals=final_results)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return self._with_cache(
            self._next_trace_server.file_content_read,
            req,
            "file_content_read",
            lambda req: req.model_dump_json(),
            lambda res: res.content,
            lambda content: tsi.FileContentReadRes(content=content),
        )

    def files_stats(self, req: tsi.FilesStatsReq) -> tsi.FilesStatsRes:
        return self._with_cache_pydantic(
            self._next_trace_server.files_stats,
            req,
            tsi.FilesStatsRes,
        )

    # Remaining Un-cacheable Methods:

    # Call API
    def call_start(self, req: tsi.CallStartReq) -> tsi.CallStartRes:
        return self._next_trace_server.call_start(req)

    def call_end(self, req: tsi.CallEndReq) -> tsi.CallEndRes:
        return self._next_trace_server.call_end(req)

    def call_read(self, req: tsi.CallReadReq) -> tsi.CallReadRes:
        return self._next_trace_server.call_read(req)

    def calls_query(self, req: tsi.CallsQueryReq) -> tsi.CallsQueryRes:
        return self._next_trace_server.calls_query(req)

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> Iterator[tsi.CallSchema]:
        return self._next_trace_server.calls_query_stream(req)

    def calls_delete(self, req: tsi.CallsDeleteReq) -> tsi.CallsDeleteRes:
        return self._next_trace_server.calls_delete(req)

    def calls_query_stats(self, req: tsi.CallsQueryStatsReq) -> tsi.CallsQueryStatsRes:
        return self._next_trace_server.calls_query_stats(req)

    def call_update(self, req: tsi.CallUpdateReq) -> tsi.CallUpdateRes:
        return self._next_trace_server.call_update(req)

    # OTEL API
    def otel_export(self, req: tsi.OtelExportReq) -> tsi.OtelExportRes:
        return self._next_trace_server.otel_export(req)

    # Op API
    def op_create(self, req: tsi.OpCreateReq) -> tsi.OpCreateRes:
        return self._next_trace_server.op_create(req)

    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        return self._next_trace_server.op_read(req)

    def ops_query(self, req: tsi.OpQueryReq) -> tsi.OpQueryRes:
        return self._next_trace_server.ops_query(req)

    # Cost API
    def cost_create(self, req: tsi.CostCreateReq) -> tsi.CostCreateRes:
        return self._next_trace_server.cost_create(req)

    def cost_query(self, req: tsi.CostQueryReq) -> tsi.CostQueryRes:
        return self._next_trace_server.cost_query(req)

    def cost_purge(self, req: tsi.CostPurgeReq) -> tsi.CostPurgeRes:
        return self._next_trace_server.cost_purge(req)

    # Obj API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        return self._next_trace_server.obj_create(req)

    def objs_query(self, req: tsi.ObjQueryReq) -> tsi.ObjQueryRes:
        return self._next_trace_server.objs_query(req)

    # Table API
    def table_create(self, req: tsi.TableCreateReq) -> tsi.TableCreateRes:
        return self._next_trace_server.table_create(req)

    def table_update(self, req: tsi.TableUpdateReq) -> tsi.TableUpdateRes:
        return self._next_trace_server.table_update(req)

    # File API
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        return self._next_trace_server.file_create(req)

    def feedback_create(self, req: tsi.FeedbackCreateReq) -> tsi.FeedbackCreateRes:
        return self._next_trace_server.feedback_create(req)

    def feedback_query(self, req: tsi.FeedbackQueryReq) -> tsi.FeedbackQueryRes:
        return self._next_trace_server.feedback_query(req)

    def feedback_purge(self, req: tsi.FeedbackPurgeReq) -> tsi.FeedbackPurgeRes:
        return self._next_trace_server.feedback_purge(req)

    def feedback_replace(self, req: tsi.FeedbackReplaceReq) -> tsi.FeedbackReplaceRes:
        return self._next_trace_server.feedback_replace(req)

    # Action API
    def actions_execute_batch(
        self, req: tsi.ActionsExecuteBatchReq
    ) -> tsi.ActionsExecuteBatchRes:
        return self._next_trace_server.actions_execute_batch(req)

    # Execute LLM API
    def completions_create(
        self, req: tsi.CompletionsCreateReq
    ) -> tsi.CompletionsCreateRes:
        return self._next_trace_server.completions_create(req)
