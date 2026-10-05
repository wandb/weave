# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional

import httpx

from ..types import v2_runtime_apply_params
from .._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
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
from ..types.v2_runtime_apply_response import V2RuntimeApplyResponse

__all__ = ["V2RuntimesResource", "AsyncV2RuntimesResource"]


class V2RuntimesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> V2RuntimesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return V2RuntimesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> V2RuntimesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return V2RuntimesResourceWithStreamingResponse(self)

    def apply(
        self,
        runtime_name: str,
        *,
        entity: str,
        project: str,
        base_url: str,
        runtime_ids: Iterable[v2_runtime_apply_params.RuntimeID],
        api_key_secret: Optional[str] | Omit = omit,
        headers: Dict[str, str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2RuntimeApplyResponse:
        """
        Create or replace a custom runtime configuration.

        Args:
          runtime_name: Stable name of the custom runtime to create or replace

          base_url: Public OpenAI-compatible endpoint base URL

          runtime_ids: Complete desired list of IDs exposed by the endpoint

          api_key_secret: Team secret name used as the endpoint API key; never the secret value

          headers: Literal headers forwarded to the endpoint

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        if not runtime_name:
            raise ValueError(f"Expected a non-empty value for `runtime_name` but received {runtime_name!r}")
        return self._put(
            path_template(
                "/v2/{entity}/{project}/runtimes/{runtime_name}",
                entity=entity,
                project=project,
                runtime_name=runtime_name,
            ),
            body=maybe_transform(
                {
                    "base_url": base_url,
                    "runtime_ids": runtime_ids,
                    "api_key_secret": api_key_secret,
                    "headers": headers,
                },
                v2_runtime_apply_params.V2RuntimeApplyParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2RuntimeApplyResponse,
        )


class AsyncV2RuntimesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncV2RuntimesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncV2RuntimesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncV2RuntimesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncV2RuntimesResourceWithStreamingResponse(self)

    async def apply(
        self,
        runtime_name: str,
        *,
        entity: str,
        project: str,
        base_url: str,
        runtime_ids: Iterable[v2_runtime_apply_params.RuntimeID],
        api_key_secret: Optional[str] | Omit = omit,
        headers: Dict[str, str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2RuntimeApplyResponse:
        """
        Create or replace a custom runtime configuration.

        Args:
          runtime_name: Stable name of the custom runtime to create or replace

          base_url: Public OpenAI-compatible endpoint base URL

          runtime_ids: Complete desired list of IDs exposed by the endpoint

          api_key_secret: Team secret name used as the endpoint API key; never the secret value

          headers: Literal headers forwarded to the endpoint

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        if not runtime_name:
            raise ValueError(f"Expected a non-empty value for `runtime_name` but received {runtime_name!r}")
        return await self._put(
            path_template(
                "/v2/{entity}/{project}/runtimes/{runtime_name}",
                entity=entity,
                project=project,
                runtime_name=runtime_name,
            ),
            body=await async_maybe_transform(
                {
                    "base_url": base_url,
                    "runtime_ids": runtime_ids,
                    "api_key_secret": api_key_secret,
                    "headers": headers,
                },
                v2_runtime_apply_params.V2RuntimeApplyParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2RuntimeApplyResponse,
        )


class V2RuntimesResourceWithRawResponse:
    def __init__(self, v2_runtimes: V2RuntimesResource) -> None:
        self._v2_runtimes = v2_runtimes

        self.apply = to_raw_response_wrapper(
            v2_runtimes.apply,
        )


class AsyncV2RuntimesResourceWithRawResponse:
    def __init__(self, v2_runtimes: AsyncV2RuntimesResource) -> None:
        self._v2_runtimes = v2_runtimes

        self.apply = async_to_raw_response_wrapper(
            v2_runtimes.apply,
        )


class V2RuntimesResourceWithStreamingResponse:
    def __init__(self, v2_runtimes: V2RuntimesResource) -> None:
        self._v2_runtimes = v2_runtimes

        self.apply = to_streamed_response_wrapper(
            v2_runtimes.apply,
        )


class AsyncV2RuntimesResourceWithStreamingResponse:
    def __init__(self, v2_runtimes: AsyncV2RuntimesResource) -> None:
        self._v2_runtimes = v2_runtimes

        self.apply = async_to_streamed_response_wrapper(
            v2_runtimes.apply,
        )
