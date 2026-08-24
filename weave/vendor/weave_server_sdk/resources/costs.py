# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional

import httpx

from ..types import cost_purge_params, cost_query_params, cost_create_params
from .._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
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
from ..types.cost_query_response import CostQueryResponse
from ..types.cost_create_response import CostCreateResponse

__all__ = ["CostsResource", "AsyncCostsResource"]


class CostsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> CostsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return CostsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> CostsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return CostsResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        costs: Dict[str, cost_create_params.Costs],
        project_id: str,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CostCreateResponse:
        """Cost Create

        Args:
          wb_user_id: Do not set directly.

        Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/cost/create",
            body=maybe_transform(
                {
                    "costs": costs,
                    "project_id": project_id,
                    "wb_user_id": wb_user_id,
                },
                cost_create_params.CostCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CostCreateResponse,
        )

    def purge(
        self,
        *,
        project_id: str,
        query: cost_purge_params.Query,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Cost Purge

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/cost/purge",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "query": query,
                },
                cost_purge_params.CostPurgeParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def query(
        self,
        *,
        project_id: str,
        fields: Optional[SequenceNotStr[str]] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        query: Optional[cost_query_params.Query] | Omit = omit,
        sort_by: Optional[Iterable[cost_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CostQueryResponse:
        """
        Cost Query

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/cost/query",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "fields": fields,
                    "limit": limit,
                    "offset": offset,
                    "query": query,
                    "sort_by": sort_by,
                },
                cost_query_params.CostQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CostQueryResponse,
        )


class AsyncCostsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncCostsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncCostsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncCostsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncCostsResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        costs: Dict[str, cost_create_params.Costs],
        project_id: str,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CostCreateResponse:
        """Cost Create

        Args:
          wb_user_id: Do not set directly.

        Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/cost/create",
            body=await async_maybe_transform(
                {
                    "costs": costs,
                    "project_id": project_id,
                    "wb_user_id": wb_user_id,
                },
                cost_create_params.CostCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CostCreateResponse,
        )

    async def purge(
        self,
        *,
        project_id: str,
        query: cost_purge_params.Query,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Cost Purge

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/cost/purge",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "query": query,
                },
                cost_purge_params.CostPurgeParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def query(
        self,
        *,
        project_id: str,
        fields: Optional[SequenceNotStr[str]] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        query: Optional[cost_query_params.Query] | Omit = omit,
        sort_by: Optional[Iterable[cost_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CostQueryResponse:
        """
        Cost Query

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/cost/query",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "fields": fields,
                    "limit": limit,
                    "offset": offset,
                    "query": query,
                    "sort_by": sort_by,
                },
                cost_query_params.CostQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CostQueryResponse,
        )


class CostsResourceWithRawResponse:
    def __init__(self, costs: CostsResource) -> None:
        self._costs = costs

        self.create = to_raw_response_wrapper(
            costs.create,
        )
        self.purge = to_raw_response_wrapper(
            costs.purge,
        )
        self.query = to_raw_response_wrapper(
            costs.query,
        )


class AsyncCostsResourceWithRawResponse:
    def __init__(self, costs: AsyncCostsResource) -> None:
        self._costs = costs

        self.create = async_to_raw_response_wrapper(
            costs.create,
        )
        self.purge = async_to_raw_response_wrapper(
            costs.purge,
        )
        self.query = async_to_raw_response_wrapper(
            costs.query,
        )


class CostsResourceWithStreamingResponse:
    def __init__(self, costs: CostsResource) -> None:
        self._costs = costs

        self.create = to_streamed_response_wrapper(
            costs.create,
        )
        self.purge = to_streamed_response_wrapper(
            costs.purge,
        )
        self.query = to_streamed_response_wrapper(
            costs.query,
        )


class AsyncCostsResourceWithStreamingResponse:
    def __init__(self, costs: AsyncCostsResource) -> None:
        self._costs = costs

        self.create = async_to_streamed_response_wrapper(
            costs.create,
        )
        self.purge = async_to_streamed_response_wrapper(
            costs.purge,
        )
        self.query = async_to_streamed_response_wrapper(
            costs.query,
        )
