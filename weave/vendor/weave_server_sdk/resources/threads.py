# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional

import httpx

from ..types import thread_stream_query_params
from .._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from .._utils import maybe_transform, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .._base_client import make_request_options

__all__ = ["ThreadsResource", "AsyncThreadsResource"]


class ThreadsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ThreadsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return ThreadsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ThreadsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return ThreadsResourceWithStreamingResponse(self)

    def stream_query(
        self,
        *,
        project_id: str,
        filter: Optional[thread_stream_query_params.Filter] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        sort_by: Optional[Iterable[thread_stream_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Threads Query Stream

        Args:
          project_id: The ID of the project

          filter: Filter criteria for the threads query

          limit: Maximum number of threads to return

          offset: Number of threads to skip

          sort_by: Sorting criteria for the threads. Supported fields: 'thread_id', 'turn_count',
              'start_time', 'last_updated', 'p50_turn_duration_ms', 'p99_turn_duration_ms'.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/threads/stream_query",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "filter": filter,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                thread_stream_query_params.ThreadStreamQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncThreadsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncThreadsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncThreadsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncThreadsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncThreadsResourceWithStreamingResponse(self)

    async def stream_query(
        self,
        *,
        project_id: str,
        filter: Optional[thread_stream_query_params.Filter] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        sort_by: Optional[Iterable[thread_stream_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Threads Query Stream

        Args:
          project_id: The ID of the project

          filter: Filter criteria for the threads query

          limit: Maximum number of threads to return

          offset: Number of threads to skip

          sort_by: Sorting criteria for the threads. Supported fields: 'thread_id', 'turn_count',
              'start_time', 'last_updated', 'p50_turn_duration_ms', 'p99_turn_duration_ms'.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/threads/stream_query",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "filter": filter,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                thread_stream_query_params.ThreadStreamQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class ThreadsResourceWithRawResponse:
    def __init__(self, threads: ThreadsResource) -> None:
        self._threads = threads

        self.stream_query = to_raw_response_wrapper(
            threads.stream_query,
        )


class AsyncThreadsResourceWithRawResponse:
    def __init__(self, threads: AsyncThreadsResource) -> None:
        self._threads = threads

        self.stream_query = async_to_raw_response_wrapper(
            threads.stream_query,
        )


class ThreadsResourceWithStreamingResponse:
    def __init__(self, threads: ThreadsResource) -> None:
        self._threads = threads

        self.stream_query = to_streamed_response_wrapper(
            threads.stream_query,
        )


class AsyncThreadsResourceWithStreamingResponse:
    def __init__(self, threads: AsyncThreadsResource) -> None:
        self._threads = threads

        self.stream_query = async_to_streamed_response_wrapper(
            threads.stream_query,
        )
