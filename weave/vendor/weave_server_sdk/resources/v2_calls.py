# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable

import httpx

from ..types import v2_call_complete_params
from .._types import Body, Query, Headers, NotGiven, not_given
from .._utils import path_template, maybe_transform, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .._base_client import make_request_options

__all__ = ["V2CallsResource", "AsyncV2CallsResource"]


class V2CallsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> V2CallsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return V2CallsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> V2CallsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return V2CallsResourceWithStreamingResponse(self)

    def complete(
        self,
        project: str,
        *,
        entity: str,
        batch: Iterable[v2_call_complete_params.Batch],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Upsert a batch of completed calls directly to the calls_complete table.

        Each call in the batch contains both start and end information. This endpoint is
        used when calls are buffered client-side and sent as complete records.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        return self._post(
            path_template("/v2/{entity}/{project}/calls/complete", entity=entity, project=project),
            body=maybe_transform({"batch": batch}, v2_call_complete_params.V2CallCompleteParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncV2CallsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncV2CallsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncV2CallsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncV2CallsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncV2CallsResourceWithStreamingResponse(self)

    async def complete(
        self,
        project: str,
        *,
        entity: str,
        batch: Iterable[v2_call_complete_params.Batch],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Upsert a batch of completed calls directly to the calls_complete table.

        Each call in the batch contains both start and end information. This endpoint is
        used when calls are buffered client-side and sent as complete records.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        return await self._post(
            path_template("/v2/{entity}/{project}/calls/complete", entity=entity, project=project),
            body=await async_maybe_transform({"batch": batch}, v2_call_complete_params.V2CallCompleteParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class V2CallsResourceWithRawResponse:
    def __init__(self, v2_calls: V2CallsResource) -> None:
        self._v2_calls = v2_calls

        self.complete = to_raw_response_wrapper(
            v2_calls.complete,
        )


class AsyncV2CallsResourceWithRawResponse:
    def __init__(self, v2_calls: AsyncV2CallsResource) -> None:
        self._v2_calls = v2_calls

        self.complete = async_to_raw_response_wrapper(
            v2_calls.complete,
        )


class V2CallsResourceWithStreamingResponse:
    def __init__(self, v2_calls: V2CallsResource) -> None:
        self._v2_calls = v2_calls

        self.complete = to_streamed_response_wrapper(
            v2_calls.complete,
        )


class AsyncV2CallsResourceWithStreamingResponse:
    def __init__(self, v2_calls: AsyncV2CallsResource) -> None:
        self._v2_calls = v2_calls

        self.complete = async_to_streamed_response_wrapper(
            v2_calls.complete,
        )
