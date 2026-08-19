# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import httpx

from ..._types import Body, Query, Headers, NotGiven, SequenceNotStr, not_given
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
from ...types.objects import alias_set_params, alias_list_params, alias_remove_params
from ...types.objects.alias_list_response import AliasListResponse

__all__ = ["AliasesResource", "AsyncAliasesResource"]


class AliasesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AliasesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AliasesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AliasesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AliasesResourceWithStreamingResponse(self)

    def list(
        self,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AliasListResponse:
        """
        List all aliases in a project.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/aliases",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"project_id": project_id}, alias_list_params.AliasListParams),
            ),
            cast_to=AliasListResponse,
        )

    def remove(
        self,
        object_id: str,
        *,
        aliases: SequenceNotStr[str],
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Remove aliases from an object.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not object_id:
            raise ValueError(f"Expected a non-empty value for `object_id` but received {object_id!r}")
        return self._post(
            path_template("/objs/{object_id}/aliases/remove", object_id=object_id),
            body=maybe_transform(
                {
                    "aliases": aliases,
                    "project_id": project_id,
                },
                alias_remove_params.AliasRemoveParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def set(
        self,
        object_id: str,
        *,
        aliases: SequenceNotStr[str],
        digest: str,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Set aliases for an object version.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not object_id:
            raise ValueError(f"Expected a non-empty value for `object_id` but received {object_id!r}")
        return self._put(
            path_template("/objs/{object_id}/aliases", object_id=object_id),
            body=maybe_transform(
                {
                    "aliases": aliases,
                    "digest": digest,
                    "project_id": project_id,
                },
                alias_set_params.AliasSetParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AsyncAliasesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncAliasesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncAliasesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncAliasesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncAliasesResourceWithStreamingResponse(self)

    async def list(
        self,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AliasListResponse:
        """
        List all aliases in a project.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/aliases",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"project_id": project_id}, alias_list_params.AliasListParams),
            ),
            cast_to=AliasListResponse,
        )

    async def remove(
        self,
        object_id: str,
        *,
        aliases: SequenceNotStr[str],
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Remove aliases from an object.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not object_id:
            raise ValueError(f"Expected a non-empty value for `object_id` but received {object_id!r}")
        return await self._post(
            path_template("/objs/{object_id}/aliases/remove", object_id=object_id),
            body=await async_maybe_transform(
                {
                    "aliases": aliases,
                    "project_id": project_id,
                },
                alias_remove_params.AliasRemoveParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def set(
        self,
        object_id: str,
        *,
        aliases: SequenceNotStr[str],
        digest: str,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Set aliases for an object version.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not object_id:
            raise ValueError(f"Expected a non-empty value for `object_id` but received {object_id!r}")
        return await self._put(
            path_template("/objs/{object_id}/aliases", object_id=object_id),
            body=await async_maybe_transform(
                {
                    "aliases": aliases,
                    "digest": digest,
                    "project_id": project_id,
                },
                alias_set_params.AliasSetParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )


class AliasesResourceWithRawResponse:
    def __init__(self, aliases: AliasesResource) -> None:
        self._aliases = aliases

        self.list = to_raw_response_wrapper(
            aliases.list,
        )
        self.remove = to_raw_response_wrapper(
            aliases.remove,
        )
        self.set = to_raw_response_wrapper(
            aliases.set,
        )


class AsyncAliasesResourceWithRawResponse:
    def __init__(self, aliases: AsyncAliasesResource) -> None:
        self._aliases = aliases

        self.list = async_to_raw_response_wrapper(
            aliases.list,
        )
        self.remove = async_to_raw_response_wrapper(
            aliases.remove,
        )
        self.set = async_to_raw_response_wrapper(
            aliases.set,
        )


class AliasesResourceWithStreamingResponse:
    def __init__(self, aliases: AliasesResource) -> None:
        self._aliases = aliases

        self.list = to_streamed_response_wrapper(
            aliases.list,
        )
        self.remove = to_streamed_response_wrapper(
            aliases.remove,
        )
        self.set = to_streamed_response_wrapper(
            aliases.set,
        )


class AsyncAliasesResourceWithStreamingResponse:
    def __init__(self, aliases: AsyncAliasesResource) -> None:
        self._aliases = aliases

        self.list = async_to_streamed_response_wrapper(
            aliases.list,
        )
        self.remove = async_to_streamed_response_wrapper(
            aliases.remove,
        )
        self.set = async_to_streamed_response_wrapper(
            aliases.set,
        )
