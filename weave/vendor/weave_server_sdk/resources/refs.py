# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import httpx

from ..types import ref_read_batch_params
from .._types import Body, Query, Headers, NotGiven, SequenceNotStr, not_given
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
from ..types.ref_read_batch_response import RefReadBatchResponse

__all__ = ["RefsResource", "AsyncRefsResource"]


class RefsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> RefsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return RefsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> RefsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return RefsResourceWithStreamingResponse(self)

    def read_batch(
        self,
        *,
        refs: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RefReadBatchResponse:
        """
        Refs Read Batch

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/refs/read_batch",
            body=maybe_transform({"refs": refs}, ref_read_batch_params.RefReadBatchParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RefReadBatchResponse,
        )


class AsyncRefsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncRefsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncRefsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncRefsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncRefsResourceWithStreamingResponse(self)

    async def read_batch(
        self,
        *,
        refs: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> RefReadBatchResponse:
        """
        Refs Read Batch

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/refs/read_batch",
            body=await async_maybe_transform({"refs": refs}, ref_read_batch_params.RefReadBatchParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=RefReadBatchResponse,
        )


class RefsResourceWithRawResponse:
    def __init__(self, refs: RefsResource) -> None:
        self._refs = refs

        self.read_batch = to_raw_response_wrapper(
            refs.read_batch,
        )


class AsyncRefsResourceWithRawResponse:
    def __init__(self, refs: AsyncRefsResource) -> None:
        self._refs = refs

        self.read_batch = async_to_raw_response_wrapper(
            refs.read_batch,
        )


class RefsResourceWithStreamingResponse:
    def __init__(self, refs: RefsResource) -> None:
        self._refs = refs

        self.read_batch = to_streamed_response_wrapper(
            refs.read_batch,
        )


class AsyncRefsResourceWithStreamingResponse:
    def __init__(self, refs: AsyncRefsResource) -> None:
        self._refs = refs

        self.read_batch = async_to_streamed_response_wrapper(
            refs.read_batch,
        )
