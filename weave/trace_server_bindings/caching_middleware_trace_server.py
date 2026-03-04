from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from collections.abc import Callable
from typing import Any, TypedDict, TypeVar

from pydantic import BaseModel
from typing_extensions import Self

from weave import version
from weave.trace.refs import ObjectRef, Ref
from weave.trace.settings import (
    server_cache_dir,
    server_cache_size_limit,
    use_server_cache,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server_bindings.caches import DiskCache, LRUCache, StackedCache
from weave.trace_server_bindings.client_interface import TraceServerClientInterface
from weave.trace_server_bindings.delegating_trace_server import (
    DelegatingTraceServerMixin,
)

logger = logging.getLogger(__name__)

TReq = TypeVar("TReq", bound=BaseModel)
TRes = TypeVar("TRes", bound=BaseModel)


class CacheRecorder(TypedDict):
    hits: int
    misses: int
    skips: int


def digest_is_cacheable(digest: str) -> bool:
    """Check if a digest is cacheable.

    Examples:
    - v1 -> False
    - oioZ7zgsCq4K7tfFQZRubx3ZGPXmFyaeoeWHHd8KUl8 -> True
    """
    # If it looks like a version, it is not cacheable
    if digest.startswith("v"):
        try:
            int(digest[1:])
        except ValueError:
            return True
        return False
    elif digest == "latest":
        return False

    return True


CACHE_DIR_PREFIX = "weave_trace_server_cache"
CACHE_KEY_SUFFIX = "v_" + version.VERSION


class CachingMiddlewareTraceServer(
    DelegatingTraceServerMixin, TraceServerClientInterface
):
    """A middleware trace server that provides caching functionality.

    This server wraps another trace server and caches responses to improve performance.
    It uses diskcache to store responses on disk and implements caching for read-only
    operations like obj_read, table_query, etc.

    Attributes:
        _next_trace_server: The underlying trace server being wrapped
        _cache: The disk cache instance used to store responses
        _cache_recorder: Metrics tracking cache hits, misses, errors and skips
    """

    _next_trace_server: TraceServerClientInterface
    _cache_prefix: str
    delegated_methods = DelegatingTraceServerMixin.delegated_methods | {"server_info"}
    optional_delegated_methods = frozenset(
        {
            "get_call_processor",
            "get_feedback_processor",
        }
    )

    def __init__(
        self,
        next_trace_server: TraceServerClientInterface,
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
        cache_dir = cache_dir or os.path.join(tempfile.gettempdir(), CACHE_DIR_PREFIX)
        self._cache = create_memory_disk_cache(cache_dir, size_limit)
        self._cache_recorder: CacheRecorder = {
            "hits": 0,
            "misses": 0,
            "skips": 0,
        }

    def __del__(self) -> None:
        """Cleanup method called when object is destroyed."""
        try:
            self._cache.close()
        except Exception:
            logger.exception("Error closing cache")

    def close(self) -> None:
        """Explicitly close cache resources (preferred over __del__)."""
        self._cache.close()

    @classmethod
    def from_env(cls, next_trace_server: TraceServerClientInterface) -> Self:
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

        res = self._cache.get(key)
        if res is not None:
            self._cache_recorder["hits"] += 1
        else:
            self._cache_recorder["misses"] += 1
        return res

    def _safe_cache_set(self, key: str, value: Any) -> None:
        """Safely store a value in cache.

        Args:
            key: The cache key
            value: The value to cache
        """
        if not use_server_cache():
            return None
        self._cache.put(key, value)
        return None

    def _safe_cache_delete(self, key: str) -> None:
        """Delete a key from cache."""
        if not use_server_cache():
            return None
        self._cache.delete(key)
        return None

    def _safe_cache_delete_prefix(self, prefix: str) -> None:
        """Delete all cached entries that start with the given prefix."""
        if not use_server_cache():
            return None

        # Get all keys and filter by prefix
        all_keys = self._cache.keys()
        keys_to_delete = [key for key in all_keys if key.startswith(prefix)]

        # Delete each matching key
        for key in keys_to_delete:
            self._cache.delete(key)

        logger.debug(f"Deleted {len(keys_to_delete)} keys with prefix '{prefix}'")

    def _make_cache_key(self, namespace: str, key: str) -> str:
        return f"{namespace}_{key}_{CACHE_KEY_SUFFIX}"

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
        of cached values.

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
            cache_key = self._make_cache_key(namespace, make_cache_key(req))
        except Exception:
            logger.exception("Error creating cache key")
            return func(req)

        # Try to get from cache
        cached_json_value = self._safe_cache_get(cache_key)
        if cached_json_value is not None:
            try:
                return deserialize(cached_json_value)
            except Exception:
                logger.exception("Error deserializing cached value")
                # Remove corrupted cache entry
                self._safe_cache_delete(cache_key)

        # Cache miss or deserialization error - get fresh result
        res = func(req)

        # Cache the result
        try:
            json_value_to_cache = serialize(res)
            self._safe_cache_set(cache_key, json_value_to_cache)
        except Exception:
            logger.exception("Error serializing value for cache")

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
            pydantic_bytes_safe_dump,
            lambda res: res.model_dump_json(),
            res_type.model_validate_json,
        )

    def reset_cache_recorder(self) -> None:
        self._cache_recorder = {
            "hits": 0,
            "misses": 0,
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

    # Obj API
    def obj_create(self, req: tsi.ObjCreateReq) -> tsi.ObjCreateRes:
        # All obj_create requests are cacheable!
        return self._with_cache_pydantic(
            self._next_trace_server.obj_create, req, tsi.ObjCreateRes
        )

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        cache_key_partial = (
            f'{{"project_id": "{req.project_id}", "object_id": "{req.object_id}"'
        )
        if req.digests:
            for digest in req.digests:
                cache_key_partial_digest = f'{cache_key_partial}, "digest": "{digest}"'
                cache_key_prefix = f"obj_read_{cache_key_partial_digest}"
                self._safe_cache_delete_prefix(cache_key_prefix)
                cache_key_prefix = f'obj_create_{{"obj": {cache_key_partial_digest}'
                self._safe_cache_delete_prefix(cache_key_prefix)
        else:
            cache_key_prefix = f"obj_read_{cache_key_partial}"
            self._safe_cache_delete_prefix(cache_key_prefix)
            cache_key_prefix = f'obj_create_{{"obj": {cache_key_partial}'
            self._safe_cache_delete_prefix(cache_key_prefix)
        return self._next_trace_server.obj_delete(req)

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        if not digest_is_cacheable(req.digest):
            return self._next_trace_server.table_query(req)
        return self._with_cache_pydantic(
            self._next_trace_server.table_query, req, tsi.TableQueryRes
        )

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

        for needed_ndx, ref in enumerate(req.refs):
            existing_result = self._safe_cache_get(
                self._make_cache_key("refs_read_batch", ref)
            )

            if existing_result is not None:
                final_results[needed_ndx] = existing_result
            else:
                needed_refs.append(ref)
                needed_indices.append(needed_ndx)

        if needed_refs:
            new_req = tsi.RefsReadBatchReq(refs=needed_refs)
            needed_results = self._next_trace_server.refs_read_batch(new_req)
            for needed_ndx, needed_ref, needed_val in zip(
                needed_indices, needed_refs, needed_results.vals, strict=False
            ):
                final_results[needed_ndx] = needed_val

                # Only cache if the ref has a cacheable digest
                try:
                    parsed_ref = Ref.parse_uri(needed_ref)
                    if isinstance(parsed_ref, ObjectRef) and digest_is_cacheable(
                        parsed_ref.digest
                    ):
                        self._safe_cache_set(
                            self._make_cache_key("refs_read_batch", needed_ref),
                            needed_val,
                        )
                except Exception:
                    logger.exception("Error parsing ref for caching")

        return tsi.RefsReadBatchRes(vals=final_results)

    # File API
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        # All file_create requests are cacheable!
        return self._with_cache_pydantic(
            self._next_trace_server.file_create, req, tsi.FileCreateRes
        )

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

    # Object APIs
    def op_read(self, req: tsi.OpReadReq) -> tsi.OpReadRes:
        if not digest_is_cacheable(req.digest):
            return self._next_trace_server.op_read(req)
        return self._with_cache_pydantic(
            self._next_trace_server.op_read, req, tsi.OpReadRes
        )

    def dataset_read(self, req: tsi.DatasetReadReq) -> tsi.DatasetReadRes:
        if not digest_is_cacheable(req.digest):
            return self._next_trace_server.dataset_read(req)
        return self._with_cache_pydantic(
            self._next_trace_server.dataset_read, req, tsi.DatasetReadRes
        )


def pydantic_bytes_safe_dump(obj: BaseModel) -> str:
    raw_dict = obj.model_dump()

    # Convert bytes to base64 string for JSON serialization
    def _bytes_to_base64(obj: Any) -> Any:
        if isinstance(obj, bytes):
            return base64.b64encode(obj).decode("utf-8")
        elif isinstance(obj, dict):
            return {k: _bytes_to_base64(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_bytes_to_base64(v) for v in obj]
        return obj

    processed_dict = _bytes_to_base64(raw_dict)
    return json.dumps(processed_dict, ensure_ascii=False)


def create_memory_disk_cache(
    cache_dir: str, size_limit: int = 1_000_000_000, memory_size: int = 1000
) -> StackedCache:
    """Factory function to create a memory+disk stacked cache.

    This is the equivalent of the old MemCacheWithDiskCacheBackend but more flexible.

    Args:
        cache_dir: Directory path for disk cache storage
        size_limit: Maximum size in bytes for disk cache (default 1GB)
        memory_size: Maximum number of items in memory cache (default 1000)

    Returns:
        A StackedCache with memory and disk layers
    """
    memory_layer: LRUCache[str, str | bytes] = LRUCache(max_size=memory_size)
    disk_layer = DiskCache(cache_dir, size_limit)

    return StackedCache(
        layers=[memory_layer, disk_layer],
        populate_on_hit=True,
        existence_check_optimization=True,  # Enable the "same key = same value" optimization
    )
