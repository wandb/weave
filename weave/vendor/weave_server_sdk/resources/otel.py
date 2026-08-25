# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import httpx

from .._types import Body, Query, Headers, NotGiven, not_given
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .._base_client import make_request_options

__all__ = ["OtelResource", "AsyncOtelResource"]


class OtelResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> OtelResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return OtelResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> OtelResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return OtelResourceWithStreamingResponse(self)

    def export(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Export Trace"""
        return self._post(
            "/otel/v1/traces",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncOtelResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncOtelResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncOtelResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncOtelResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncOtelResourceWithStreamingResponse(self)

    async def export(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Export Trace"""
        return await self._post(
            "/otel/v1/traces",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class OtelResourceWithRawResponse:
    def __init__(self, otel: OtelResource) -> None:
        self._otel = otel

        self.export = to_raw_response_wrapper(
            otel.export,
        )


class AsyncOtelResourceWithRawResponse:
    def __init__(self, otel: AsyncOtelResource) -> None:
        self._otel = otel

        self.export = async_to_raw_response_wrapper(
            otel.export,
        )


class OtelResourceWithStreamingResponse:
    def __init__(self, otel: OtelResource) -> None:
        self._otel = otel

        self.export = to_streamed_response_wrapper(
            otel.export,
        )


class AsyncOtelResourceWithStreamingResponse:
    def __init__(self, otel: AsyncOtelResource) -> None:
        self._otel = otel

        self.export = async_to_streamed_response_wrapper(
            otel.export,
        )
