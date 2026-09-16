# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union, Iterable, Optional
from datetime import datetime

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from ..._utils import maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.agents import span_query_params, span_stats_params, span_custom_attrs_schema_params
from ...types.agents.span_query_response import SpanQueryResponse
from ...types.agents.span_stats_response import SpanStatsResponse
from ...types.agents.span_custom_attrs_schema_response import SpanCustomAttrsSchemaResponse

__all__ = ["SpansResource", "AsyncSpansResource"]


class SpansResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> SpansResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return SpansResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> SpansResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return SpansResourceWithStreamingResponse(self)

    def custom_attrs_schema(
        self,
        *,
        project_id: str,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        query: Optional[span_custom_attrs_schema_params.Query] | Omit = omit,
        started_after: Union[str, datetime, None] | Omit = omit,
        started_before: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SpanCustomAttrsSchemaResponse:
        """
        Discover typed custom attribute keys on matching agent spans.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/agents/spans/custom-attrs/schema",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "limit": limit,
                    "offset": offset,
                    "query": query,
                    "started_after": started_after,
                    "started_before": started_before,
                },
                span_custom_attrs_schema_params.SpanCustomAttrsSchemaParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SpanCustomAttrsSchemaResponse,
        )

    def query(
        self,
        *,
        project_id: str,
        custom_attr_columns: Iterable[span_query_params.CustomAttrColumn] | Omit = omit,
        group_by: Optional[Iterable[span_query_params.GroupBy]] | Omit = omit,
        group_distributions: Iterable[span_query_params.GroupDistribution] | Omit = omit,
        group_filters: Iterable[span_query_params.GroupFilter] | Omit = omit,
        include_costs: bool | Omit = omit,
        include_details: bool | Omit = omit,
        limit: int | Omit = omit,
        measures: Iterable[span_query_params.Measure] | Omit = omit,
        offset: int | Omit = omit,
        query: Optional[span_query_params.Query] | Omit = omit,
        signal_filters: Optional[span_query_params.SignalFilters] | Omit = omit,
        sort_by: Optional[Iterable[span_query_params.SortBy]] | Omit = omit,
        started_after: Union[str, datetime, None] | Omit = omit,
        started_before: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SpanQueryResponse:
        """
        Query agent spans, either as raw rows or grouped aggregates.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/agents/spans/query",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "custom_attr_columns": custom_attr_columns,
                    "group_by": group_by,
                    "group_distributions": group_distributions,
                    "group_filters": group_filters,
                    "include_costs": include_costs,
                    "include_details": include_details,
                    "limit": limit,
                    "measures": measures,
                    "offset": offset,
                    "query": query,
                    "signal_filters": signal_filters,
                    "sort_by": sort_by,
                    "started_after": started_after,
                    "started_before": started_before,
                },
                span_query_params.SpanQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SpanQueryResponse,
        )

    def stats(
        self,
        *,
        project_id: str,
        start: Union[str, datetime],
        bucket_by: Optional[span_stats_params.BucketBy] | Omit = omit,
        end: Union[str, datetime, None] | Omit = omit,
        granularity: Optional[int] | Omit = omit,
        group_by: Iterable[span_stats_params.GroupBy] | Omit = omit,
        group_filters: Iterable[span_stats_params.GroupFilter] | Omit = omit,
        group_limit: int | Omit = omit,
        metrics: Iterable[span_stats_params.Metric] | Omit = omit,
        query: Optional[span_stats_params.Query] | Omit = omit,
        signal_filters: Optional[span_stats_params.SignalFilters] | Omit = omit,
        timezone: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SpanStatsResponse:
        """
        Query chart-ready aggregations over agent spans.

        Args:
          bucket_by: Bucket stats rows by started_at time intervals.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/agents/spans/stats",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "start": start,
                    "bucket_by": bucket_by,
                    "end": end,
                    "granularity": granularity,
                    "group_by": group_by,
                    "group_filters": group_filters,
                    "group_limit": group_limit,
                    "metrics": metrics,
                    "query": query,
                    "signal_filters": signal_filters,
                    "timezone": timezone,
                },
                span_stats_params.SpanStatsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SpanStatsResponse,
        )


class AsyncSpansResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncSpansResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncSpansResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncSpansResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncSpansResourceWithStreamingResponse(self)

    async def custom_attrs_schema(
        self,
        *,
        project_id: str,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        query: Optional[span_custom_attrs_schema_params.Query] | Omit = omit,
        started_after: Union[str, datetime, None] | Omit = omit,
        started_before: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SpanCustomAttrsSchemaResponse:
        """
        Discover typed custom attribute keys on matching agent spans.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/agents/spans/custom-attrs/schema",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "limit": limit,
                    "offset": offset,
                    "query": query,
                    "started_after": started_after,
                    "started_before": started_before,
                },
                span_custom_attrs_schema_params.SpanCustomAttrsSchemaParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SpanCustomAttrsSchemaResponse,
        )

    async def query(
        self,
        *,
        project_id: str,
        custom_attr_columns: Iterable[span_query_params.CustomAttrColumn] | Omit = omit,
        group_by: Optional[Iterable[span_query_params.GroupBy]] | Omit = omit,
        group_distributions: Iterable[span_query_params.GroupDistribution] | Omit = omit,
        group_filters: Iterable[span_query_params.GroupFilter] | Omit = omit,
        include_costs: bool | Omit = omit,
        include_details: bool | Omit = omit,
        limit: int | Omit = omit,
        measures: Iterable[span_query_params.Measure] | Omit = omit,
        offset: int | Omit = omit,
        query: Optional[span_query_params.Query] | Omit = omit,
        signal_filters: Optional[span_query_params.SignalFilters] | Omit = omit,
        sort_by: Optional[Iterable[span_query_params.SortBy]] | Omit = omit,
        started_after: Union[str, datetime, None] | Omit = omit,
        started_before: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SpanQueryResponse:
        """
        Query agent spans, either as raw rows or grouped aggregates.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/agents/spans/query",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "custom_attr_columns": custom_attr_columns,
                    "group_by": group_by,
                    "group_distributions": group_distributions,
                    "group_filters": group_filters,
                    "include_costs": include_costs,
                    "include_details": include_details,
                    "limit": limit,
                    "measures": measures,
                    "offset": offset,
                    "query": query,
                    "signal_filters": signal_filters,
                    "sort_by": sort_by,
                    "started_after": started_after,
                    "started_before": started_before,
                },
                span_query_params.SpanQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SpanQueryResponse,
        )

    async def stats(
        self,
        *,
        project_id: str,
        start: Union[str, datetime],
        bucket_by: Optional[span_stats_params.BucketBy] | Omit = omit,
        end: Union[str, datetime, None] | Omit = omit,
        granularity: Optional[int] | Omit = omit,
        group_by: Iterable[span_stats_params.GroupBy] | Omit = omit,
        group_filters: Iterable[span_stats_params.GroupFilter] | Omit = omit,
        group_limit: int | Omit = omit,
        metrics: Iterable[span_stats_params.Metric] | Omit = omit,
        query: Optional[span_stats_params.Query] | Omit = omit,
        signal_filters: Optional[span_stats_params.SignalFilters] | Omit = omit,
        timezone: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> SpanStatsResponse:
        """
        Query chart-ready aggregations over agent spans.

        Args:
          bucket_by: Bucket stats rows by started_at time intervals.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/agents/spans/stats",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "start": start,
                    "bucket_by": bucket_by,
                    "end": end,
                    "granularity": granularity,
                    "group_by": group_by,
                    "group_filters": group_filters,
                    "group_limit": group_limit,
                    "metrics": metrics,
                    "query": query,
                    "signal_filters": signal_filters,
                    "timezone": timezone,
                },
                span_stats_params.SpanStatsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=SpanStatsResponse,
        )


class SpansResourceWithRawResponse:
    def __init__(self, spans: SpansResource) -> None:
        self._spans = spans

        self.custom_attrs_schema = to_raw_response_wrapper(
            spans.custom_attrs_schema,
        )
        self.query = to_raw_response_wrapper(
            spans.query,
        )
        self.stats = to_raw_response_wrapper(
            spans.stats,
        )


class AsyncSpansResourceWithRawResponse:
    def __init__(self, spans: AsyncSpansResource) -> None:
        self._spans = spans

        self.custom_attrs_schema = async_to_raw_response_wrapper(
            spans.custom_attrs_schema,
        )
        self.query = async_to_raw_response_wrapper(
            spans.query,
        )
        self.stats = async_to_raw_response_wrapper(
            spans.stats,
        )


class SpansResourceWithStreamingResponse:
    def __init__(self, spans: SpansResource) -> None:
        self._spans = spans

        self.custom_attrs_schema = to_streamed_response_wrapper(
            spans.custom_attrs_schema,
        )
        self.query = to_streamed_response_wrapper(
            spans.query,
        )
        self.stats = to_streamed_response_wrapper(
            spans.stats,
        )


class AsyncSpansResourceWithStreamingResponse:
    def __init__(self, spans: AsyncSpansResource) -> None:
        self._spans = spans

        self.custom_attrs_schema = async_to_streamed_response_wrapper(
            spans.custom_attrs_schema,
        )
        self.query = async_to_streamed_response_wrapper(
            spans.query,
        )
        self.stats = async_to_streamed_response_wrapper(
            spans.stats,
        )
