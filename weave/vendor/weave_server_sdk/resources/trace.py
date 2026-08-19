# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional

import httpx

from ..types import trace_usage_params
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
from ..types.trace_usage_response import TraceUsageResponse

__all__ = ["TraceResource", "AsyncTraceResource"]


class TraceResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> TraceResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return TraceResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> TraceResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return TraceResourceWithStreamingResponse(self)

    def usage(
        self,
        *,
        project_id: str,
        filter: Optional[trace_usage_params.Filter] | Omit = omit,
        include_costs: bool | Omit = omit,
        limit: int | Omit = omit,
        query: Optional[trace_usage_params.Query] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TraceUsageResponse:
        """
        Compute per-call usage for a trace, with descendant rollup.

        Args:
          filter: Filter to select calls. Typically use trace_ids to get all calls in a trace.

          include_costs: If true, include cost calculations in the usage.

          limit: Maximum number of calls to process. Acts as a safety limit to prevent unbounded
              memory usage.

          query: Additional query conditions for filtering calls.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/trace/usage",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "filter": filter,
                    "include_costs": include_costs,
                    "limit": limit,
                    "query": query,
                },
                trace_usage_params.TraceUsageParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TraceUsageResponse,
        )


class AsyncTraceResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncTraceResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncTraceResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncTraceResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncTraceResourceWithStreamingResponse(self)

    async def usage(
        self,
        *,
        project_id: str,
        filter: Optional[trace_usage_params.Filter] | Omit = omit,
        include_costs: bool | Omit = omit,
        limit: int | Omit = omit,
        query: Optional[trace_usage_params.Query] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TraceUsageResponse:
        """
        Compute per-call usage for a trace, with descendant rollup.

        Args:
          filter: Filter to select calls. Typically use trace_ids to get all calls in a trace.

          include_costs: If true, include cost calculations in the usage.

          limit: Maximum number of calls to process. Acts as a safety limit to prevent unbounded
              memory usage.

          query: Additional query conditions for filtering calls.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/trace/usage",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "filter": filter,
                    "include_costs": include_costs,
                    "limit": limit,
                    "query": query,
                },
                trace_usage_params.TraceUsageParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TraceUsageResponse,
        )


class TraceResourceWithRawResponse:
    def __init__(self, trace: TraceResource) -> None:
        self._trace = trace

        self.usage = to_raw_response_wrapper(
            trace.usage,
        )


class AsyncTraceResourceWithRawResponse:
    def __init__(self, trace: AsyncTraceResource) -> None:
        self._trace = trace

        self.usage = async_to_raw_response_wrapper(
            trace.usage,
        )


class TraceResourceWithStreamingResponse:
    def __init__(self, trace: TraceResource) -> None:
        self._trace = trace

        self.usage = to_streamed_response_wrapper(
            trace.usage,
        )


class AsyncTraceResourceWithStreamingResponse:
    def __init__(self, trace: AsyncTraceResource) -> None:
        self._trace = trace

        self.usage = async_to_streamed_response_wrapper(
            trace.usage,
        )
