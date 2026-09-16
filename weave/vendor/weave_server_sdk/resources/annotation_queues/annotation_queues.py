# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional

import httpx

from .items import (
    ItemsResource,
    AsyncItemsResource,
    ItemsResourceWithRawResponse,
    AsyncItemsResourceWithRawResponse,
    ItemsResourceWithStreamingResponse,
    AsyncItemsResourceWithStreamingResponse,
)
from ...types import (
    annotation_queue_read_params,
    annotation_queue_query_params,
    annotation_queue_stats_params,
    annotation_queue_create_params,
    annotation_queue_delete_params,
    annotation_queue_update_params,
)
from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import path_template, maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ..._decoders.jsonl import JSONLDecoder, AsyncJSONLDecoder
from ...types.annotation_queue_schema import AnnotationQueueSchema
from ...types.annotation_queue_read_response import AnnotationQueueReadResponse
from ...types.annotation_queue_stats_response import AnnotationQueueStatsResponse
from ...types.annotation_queue_create_response import AnnotationQueueCreateResponse
from ...types.annotation_queue_delete_response import AnnotationQueueDeleteResponse
from ...types.annotation_queue_update_response import AnnotationQueueUpdateResponse

__all__ = ["AnnotationQueuesResource", "AsyncAnnotationQueuesResource"]


class AnnotationQueuesResource(SyncAPIResource):
    @cached_property
    def items(self) -> ItemsResource:
        return ItemsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AnnotationQueuesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AnnotationQueuesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AnnotationQueuesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AnnotationQueuesResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        name: str,
        project_id: str,
        scorer_refs: SequenceNotStr[str],
        description: str | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueCreateResponse:
        """Create a new annotation queue.

        Args:
          wb_user_id: Do not set directly.

        Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/annotation_queues",
            body=maybe_transform(
                {
                    "name": name,
                    "project_id": project_id,
                    "scorer_refs": scorer_refs,
                    "description": description,
                    "wb_user_id": wb_user_id,
                },
                annotation_queue_create_params.AnnotationQueueCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueCreateResponse,
        )

    def update(
        self,
        queue_id: str,
        *,
        project_id: str,
        description: Optional[str] | Omit = omit,
        name: Optional[str] | Omit = omit,
        scorer_refs: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueUpdateResponse:
        """
        Update an annotation queue's metadata (name, description, scorer_refs).

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._put(
            path_template("/annotation_queues/{queue_id}", queue_id=queue_id),
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "description": description,
                    "name": name,
                    "scorer_refs": scorer_refs,
                },
                annotation_queue_update_params.AnnotationQueueUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueUpdateResponse,
        )

    def delete(
        self,
        queue_id: str,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueDeleteResponse:
        """
        Delete (soft-delete) an annotation queue.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._delete(
            path_template("/annotation_queues/{queue_id}", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"project_id": project_id}, annotation_queue_delete_params.AnnotationQueueDeleteParams
                ),
            ),
            cast_to=AnnotationQueueDeleteResponse,
        )

    def query(
        self,
        *,
        project_id: str,
        limit: Optional[int] | Omit = omit,
        name: Optional[str] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        sort_by: Optional[Iterable[annotation_queue_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> JSONLDecoder[AnnotationQueueSchema]:
        """
        Query annotation queues for a project (streaming NDJSON response).

        Args:
          name: Filter by queue name (case-insensitive partial match)

          sort_by: Sort by multiple fields (e.g., created_at, updated_at, name)

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {"Accept": "application/x-ndjson", **(extra_headers or {})}
        return self._post(
            "/annotation_queues/query",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "limit": limit,
                    "name": name,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                annotation_queue_query_params.AnnotationQueueQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=JSONLDecoder[AnnotationQueueSchema],
            stream=True,
        )

    def read(
        self,
        queue_id: str,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueReadResponse:
        """
        Read a specific annotation queue.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._get(
            path_template("/annotation_queues/{queue_id}", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"project_id": project_id}, annotation_queue_read_params.AnnotationQueueReadParams
                ),
            ),
            cast_to=AnnotationQueueReadResponse,
        )

    def stats(
        self,
        *,
        project_id: str,
        queue_ids: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueStatsResponse:
        """
        Get stats for multiple annotation queues.

        Args:
          queue_ids: List of queue IDs to get stats for

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/annotation_queues/stats",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "queue_ids": queue_ids,
                },
                annotation_queue_stats_params.AnnotationQueueStatsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueStatsResponse,
        )


class AsyncAnnotationQueuesResource(AsyncAPIResource):
    @cached_property
    def items(self) -> AsyncItemsResource:
        return AsyncItemsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncAnnotationQueuesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncAnnotationQueuesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncAnnotationQueuesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncAnnotationQueuesResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        name: str,
        project_id: str,
        scorer_refs: SequenceNotStr[str],
        description: str | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueCreateResponse:
        """Create a new annotation queue.

        Args:
          wb_user_id: Do not set directly.

        Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/annotation_queues",
            body=await async_maybe_transform(
                {
                    "name": name,
                    "project_id": project_id,
                    "scorer_refs": scorer_refs,
                    "description": description,
                    "wb_user_id": wb_user_id,
                },
                annotation_queue_create_params.AnnotationQueueCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueCreateResponse,
        )

    async def update(
        self,
        queue_id: str,
        *,
        project_id: str,
        description: Optional[str] | Omit = omit,
        name: Optional[str] | Omit = omit,
        scorer_refs: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueUpdateResponse:
        """
        Update an annotation queue's metadata (name, description, scorer_refs).

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._put(
            path_template("/annotation_queues/{queue_id}", queue_id=queue_id),
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "description": description,
                    "name": name,
                    "scorer_refs": scorer_refs,
                },
                annotation_queue_update_params.AnnotationQueueUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueUpdateResponse,
        )

    async def delete(
        self,
        queue_id: str,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueDeleteResponse:
        """
        Delete (soft-delete) an annotation queue.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._delete(
            path_template("/annotation_queues/{queue_id}", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"project_id": project_id}, annotation_queue_delete_params.AnnotationQueueDeleteParams
                ),
            ),
            cast_to=AnnotationQueueDeleteResponse,
        )

    async def query(
        self,
        *,
        project_id: str,
        limit: Optional[int] | Omit = omit,
        name: Optional[str] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        sort_by: Optional[Iterable[annotation_queue_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncJSONLDecoder[AnnotationQueueSchema]:
        """
        Query annotation queues for a project (streaming NDJSON response).

        Args:
          name: Filter by queue name (case-insensitive partial match)

          sort_by: Sort by multiple fields (e.g., created_at, updated_at, name)

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {"Accept": "application/x-ndjson", **(extra_headers or {})}
        return await self._post(
            "/annotation_queues/query",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "limit": limit,
                    "name": name,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                annotation_queue_query_params.AnnotationQueueQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AsyncJSONLDecoder[AnnotationQueueSchema],
            stream=True,
        )

    async def read(
        self,
        queue_id: str,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueReadResponse:
        """
        Read a specific annotation queue.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._get(
            path_template("/annotation_queues/{queue_id}", queue_id=queue_id),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"project_id": project_id}, annotation_queue_read_params.AnnotationQueueReadParams
                ),
            ),
            cast_to=AnnotationQueueReadResponse,
        )

    async def stats(
        self,
        *,
        project_id: str,
        queue_ids: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AnnotationQueueStatsResponse:
        """
        Get stats for multiple annotation queues.

        Args:
          queue_ids: List of queue IDs to get stats for

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/annotation_queues/stats",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "queue_ids": queue_ids,
                },
                annotation_queue_stats_params.AnnotationQueueStatsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AnnotationQueueStatsResponse,
        )


class AnnotationQueuesResourceWithRawResponse:
    def __init__(self, annotation_queues: AnnotationQueuesResource) -> None:
        self._annotation_queues = annotation_queues

        self.create = to_raw_response_wrapper(
            annotation_queues.create,
        )
        self.update = to_raw_response_wrapper(
            annotation_queues.update,
        )
        self.delete = to_raw_response_wrapper(
            annotation_queues.delete,
        )
        self.query = to_raw_response_wrapper(
            annotation_queues.query,
        )
        self.read = to_raw_response_wrapper(
            annotation_queues.read,
        )
        self.stats = to_raw_response_wrapper(
            annotation_queues.stats,
        )

    @cached_property
    def items(self) -> ItemsResourceWithRawResponse:
        return ItemsResourceWithRawResponse(self._annotation_queues.items)


class AsyncAnnotationQueuesResourceWithRawResponse:
    def __init__(self, annotation_queues: AsyncAnnotationQueuesResource) -> None:
        self._annotation_queues = annotation_queues

        self.create = async_to_raw_response_wrapper(
            annotation_queues.create,
        )
        self.update = async_to_raw_response_wrapper(
            annotation_queues.update,
        )
        self.delete = async_to_raw_response_wrapper(
            annotation_queues.delete,
        )
        self.query = async_to_raw_response_wrapper(
            annotation_queues.query,
        )
        self.read = async_to_raw_response_wrapper(
            annotation_queues.read,
        )
        self.stats = async_to_raw_response_wrapper(
            annotation_queues.stats,
        )

    @cached_property
    def items(self) -> AsyncItemsResourceWithRawResponse:
        return AsyncItemsResourceWithRawResponse(self._annotation_queues.items)


class AnnotationQueuesResourceWithStreamingResponse:
    def __init__(self, annotation_queues: AnnotationQueuesResource) -> None:
        self._annotation_queues = annotation_queues

        self.create = to_streamed_response_wrapper(
            annotation_queues.create,
        )
        self.update = to_streamed_response_wrapper(
            annotation_queues.update,
        )
        self.delete = to_streamed_response_wrapper(
            annotation_queues.delete,
        )
        self.query = to_streamed_response_wrapper(
            annotation_queues.query,
        )
        self.read = to_streamed_response_wrapper(
            annotation_queues.read,
        )
        self.stats = to_streamed_response_wrapper(
            annotation_queues.stats,
        )

    @cached_property
    def items(self) -> ItemsResourceWithStreamingResponse:
        return ItemsResourceWithStreamingResponse(self._annotation_queues.items)


class AsyncAnnotationQueuesResourceWithStreamingResponse:
    def __init__(self, annotation_queues: AsyncAnnotationQueuesResource) -> None:
        self._annotation_queues = annotation_queues

        self.create = async_to_streamed_response_wrapper(
            annotation_queues.create,
        )
        self.update = async_to_streamed_response_wrapper(
            annotation_queues.update,
        )
        self.delete = async_to_streamed_response_wrapper(
            annotation_queues.delete,
        )
        self.query = async_to_streamed_response_wrapper(
            annotation_queues.query,
        )
        self.read = async_to_streamed_response_wrapper(
            annotation_queues.read,
        )
        self.stats = async_to_streamed_response_wrapper(
            annotation_queues.stats,
        )

    @cached_property
    def items(self) -> AsyncItemsResourceWithStreamingResponse:
        return AsyncItemsResourceWithStreamingResponse(self._annotation_queues.items)
