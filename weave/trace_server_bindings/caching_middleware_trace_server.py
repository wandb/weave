from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Callable

import diskcache

from weave.trace_server import trace_server_interface as tsi

logger = logging.getLogger(__name__)


class CachingMiddlewareTraceServer(tsi.TraceServerInterface):
    _next_trace_server: tsi.TraceServerInterface
    _cache_prefix: str

    def __init__(
        self,
        next_trace_server: tsi.TraceServerInterface,
        cache_dir: Path | None = None,  # todo make this configurable
        size_limit: int = 1_000_000_000,  # 1GB - todo make this configurable
    ):
        self._next_trace_server = next_trace_server

        self._cache = diskcache.Cache(cache_dir, size_limit=size_limit)

    def _safe_cache_get(self, key: str) -> Any:
        try:
            use_cache = os.getenv("WEAVE_USE_SERVER_CACHE", "true").lower() == "true"
            if not use_cache:
                return None
            return self._cache.get(key)
        except Exception as e:
            logger.exception(f"Error getting cached value: {e}")
            return None

    def _safe_cache_set(self, key: str, value: Any) -> None:
        try:
            return self._cache.set(key, value)
        except Exception as e:
            logger.exception(f"Error caching value: {e}")

    def _safe_cache_delete(self, key: str) -> None:
        try:
            self._cache.delete(key)
        except Exception as e:
            logger.exception(f"Error deleting cached value: {e}")

    def _with_cache(
        self,
        namespace: str,
        make_cache_key: Callable[[Any], str],
        func: Callable[[Any], Any],
        req: Any,
        serialize: Callable[[Any], str],
        deserialize: Callable[[Any], Any],
    ) -> Any:
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

    def _with_cache_generic(self, func, req, res_type: type[tsi.BaseModel]):
        return self._with_cache(
            func.__name__,
            lambda req: req.model_dump_json(),
            func,
            req,
            lambda res: res.model_dump_json(),
            lambda json_value: res_type.model_validate_json(json_value),
        )

    # Cacheable Methods:
    def obj_read(self, req: tsi.ObjReadReq) -> tsi.ObjReadRes:
        return self._with_cache_generic(
            self._next_trace_server.obj_read, req, tsi.ObjReadRes
        )

    def table_query(self, req: tsi.TableQueryReq) -> tsi.TableQueryRes:
        return self._with_cache_generic(
            self._next_trace_server.table_query, req, tsi.TableQueryRes
        )

    def table_query_stream(
        self, req: tsi.TableQueryReq
    ) -> Iterator[tsi.TableRowSchema]:
        # I am not sure the best way to cache the iterator here. TODO
        return self._next_trace_server.table_query_stream(req)

    def table_query_stats(self, req: tsi.TableQueryStatsReq) -> tsi.TableQueryStatsRes:
        return self._with_cache_generic(
            self._next_trace_server.table_query_stats, req, tsi.TableQueryStatsRes
        )

    def refs_read_batch(self, req: tsi.RefsReadBatchReq) -> tsi.RefsReadBatchRes:
        # This is a special case because we want to cache individual refs and only
        # query for the ones that are not in the cache.

        # 1. Find the refs that are not in the cache
        # 2. Query for the refs that are not in the cache
        # 3. Cache the refs that are not in the cache
        # 4. Return the re-composed response.

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
                    self._safe_cache_set(ref, val)
                except Exception as e:
                    logger.exception(f"Error caching values: {e}")

        return tsi.RefsReadBatchRes(vals=final_results)

    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        return self._with_cache(
            "file_content_read",
            lambda req: req.model_dump_json(),
            self._next_trace_server.file_content_read,
            req,
            lambda res: res.content,
            lambda content: tsi.FileContentReadRes(content=content),
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

    def obj_delete(self, req: tsi.ObjDeleteReq) -> tsi.ObjDeleteRes:
        return self._next_trace_server.obj_delete(req)

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
