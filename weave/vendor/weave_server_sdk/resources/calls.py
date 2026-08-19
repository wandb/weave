# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional

import httpx

from ..types import (
    call_end_params,
    call_read_params,
    call_start_params,
    call_usage_params,
    call_delete_params,
    call_update_params,
    call_query_stats_params,
    call_stream_query_params,
    call_upsert_batch_params,
)
from .._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from .._utils import maybe_transform, strip_not_given, async_maybe_transform
from .._compat import cached_property
from .._resource import SyncAPIResource, AsyncAPIResource
from .._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .._base_client import make_request_options
from .._decoders.jsonl import JSONLDecoder, AsyncJSONLDecoder
from ..types.call_read_response import CallReadResponse
from ..types.call_start_response import CallStartResponse
from ..types.call_usage_response import CallUsageResponse
from ..types.call_delete_response import CallDeleteResponse
from ..types.call_query_stats_response import CallQueryStatsResponse
from ..types.call_upsert_batch_response import CallUpsertBatchResponse

__all__ = ["CallsResource", "AsyncCallsResource"]


class CallsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> CallsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return CallsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> CallsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return CallsResourceWithStreamingResponse(self)

    def update(
        self,
        *,
        call_id: str,
        project_id: str,
        display_name: Optional[str] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Call Update

        Args:
          wb_user_id: Do not set directly.

        Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/call/update",
            body=maybe_transform(
                {
                    "call_id": call_id,
                    "project_id": project_id,
                    "display_name": display_name,
                    "wb_user_id": wb_user_id,
                },
                call_update_params.CallUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def delete(
        self,
        *,
        call_ids: SequenceNotStr[str],
        project_id: str,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallDeleteResponse:
        """Calls Delete

        Args:
          wb_user_id: Do not set directly.

        Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/calls/delete",
            body=maybe_transform(
                {
                    "call_ids": call_ids,
                    "project_id": project_id,
                    "wb_user_id": wb_user_id,
                },
                call_delete_params.CallDeleteParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallDeleteResponse,
        )

    def end(
        self,
        *,
        end: call_end_params.End,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Call End

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/call/end",
            body=maybe_transform({"end": end}, call_end_params.CallEndParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def query_stats(
        self,
        *,
        project_id: str,
        expand_columns: Optional[SequenceNotStr[str]] | Omit = omit,
        filter: Optional[call_query_stats_params.Filter] | Omit = omit,
        include_total_storage_size: Optional[bool] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        query: Optional[call_query_stats_params.Query] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallQueryStatsResponse:
        """
        Calls Query Stats

        Args:
          expand_columns: Columns with refs to objects or table rows that require expansion during
              filtering or ordering.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/calls/query_stats",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "expand_columns": expand_columns,
                    "filter": filter,
                    "include_total_storage_size": include_total_storage_size,
                    "limit": limit,
                    "query": query,
                },
                call_query_stats_params.CallQueryStatsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallQueryStatsResponse,
        )

    def read(
        self,
        *,
        id: str,
        project_id: str,
        include_costs: Optional[bool] | Omit = omit,
        include_storage_size: Optional[bool] | Omit = omit,
        include_total_storage_size: Optional[bool] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallReadResponse:
        """
        Call Read

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/call/read",
            body=maybe_transform(
                {
                    "id": id,
                    "project_id": project_id,
                    "include_costs": include_costs,
                    "include_storage_size": include_storage_size,
                    "include_total_storage_size": include_total_storage_size,
                },
                call_read_params.CallReadParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallReadResponse,
        )

    def start(
        self,
        *,
        start: call_start_params.Start,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallStartResponse:
        """
        Call Start

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/call/start",
            body=maybe_transform({"start": start}, call_start_params.CallStartParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallStartResponse,
        )

    def stream_query(
        self,
        *,
        project_id: str,
        columns: Optional[SequenceNotStr[str]] | Omit = omit,
        expand_columns: Optional[SequenceNotStr[str]] | Omit = omit,
        filter: Optional[call_stream_query_params.Filter] | Omit = omit,
        include_costs: Optional[bool] | Omit = omit,
        include_feedback: Optional[bool] | Omit = omit,
        include_storage_size: Optional[bool] | Omit = omit,
        include_total_storage_size: Optional[bool] | Omit = omit,
        include_usernames: Optional[bool] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        query: Optional[call_stream_query_params.Query] | Omit = omit,
        return_expanded_column_values: Optional[bool] | Omit = omit,
        sort_by: Optional[Iterable[call_stream_query_params.SortBy]] | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> JSONLDecoder[object]:
        """Calls Query Stream

        Args:
          expand_columns: Columns to expand, i.e.

        refs to other objects

          include_costs: Beta, subject to change. If true, the response will include any model costs for
              each call.

          include_feedback: Beta, subject to change. If true, the response will include feedback for each
              call.

          include_storage_size: Beta, subject to change. If true, the response will include the storage size for
              a call.

          include_total_storage_size: Beta, subject to change. If true, the response will include the total storage
              size for a trace.

          include_usernames: If true, the response will attempt to resolve each call's wb_user_id to a
              username for the duration of this request.

          return_expanded_column_values: If true, the response will include raw values for expanded columns. If false,
              the response expand_columns will only be used for filtering and ordering. This
              is useful for clients that want to resolve refs themselves, e.g. for performance
              reasons.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {"Accept": "application/jsonl", **(extra_headers or {})}
        extra_headers = {**strip_not_given({"accept": accept}), **(extra_headers or {})}
        return self._post(
            "/calls/stream_query",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "columns": columns,
                    "expand_columns": expand_columns,
                    "filter": filter,
                    "include_costs": include_costs,
                    "include_feedback": include_feedback,
                    "include_storage_size": include_storage_size,
                    "include_total_storage_size": include_total_storage_size,
                    "include_usernames": include_usernames,
                    "limit": limit,
                    "offset": offset,
                    "query": query,
                    "return_expanded_column_values": return_expanded_column_values,
                    "sort_by": sort_by,
                },
                call_stream_query_params.CallStreamQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=JSONLDecoder[object],
            stream=True,
        )

    def upsert_batch(
        self,
        *,
        batch: Iterable[call_upsert_batch_params.Batch],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallUpsertBatchResponse:
        """
        Call Start Batch

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/call/upsert_batch",
            body=maybe_transform({"batch": batch}, call_upsert_batch_params.CallUpsertBatchParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallUpsertBatchResponse,
        )

    def usage(
        self,
        *,
        call_ids: SequenceNotStr[str],
        project_id: str,
        include_costs: bool | Omit = omit,
        limit: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallUsageResponse:
        """
        Compute aggregated usage for multiple root calls, with descendant rollup.

        Args:
          call_ids: Root call IDs to aggregate. Each result key corresponds to one input call ID.

          include_costs: If true, include cost calculations in the usage.

          limit: Maximum number of calls to process across all traces. Acts as a safety limit to
              prevent unbounded memory usage.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/calls/usage",
            body=maybe_transform(
                {
                    "call_ids": call_ids,
                    "project_id": project_id,
                    "include_costs": include_costs,
                    "limit": limit,
                },
                call_usage_params.CallUsageParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallUsageResponse,
        )


class AsyncCallsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncCallsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncCallsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncCallsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncCallsResourceWithStreamingResponse(self)

    async def update(
        self,
        *,
        call_id: str,
        project_id: str,
        display_name: Optional[str] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Call Update

        Args:
          wb_user_id: Do not set directly.

        Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/call/update",
            body=await async_maybe_transform(
                {
                    "call_id": call_id,
                    "project_id": project_id,
                    "display_name": display_name,
                    "wb_user_id": wb_user_id,
                },
                call_update_params.CallUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def delete(
        self,
        *,
        call_ids: SequenceNotStr[str],
        project_id: str,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallDeleteResponse:
        """Calls Delete

        Args:
          wb_user_id: Do not set directly.

        Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/calls/delete",
            body=await async_maybe_transform(
                {
                    "call_ids": call_ids,
                    "project_id": project_id,
                    "wb_user_id": wb_user_id,
                },
                call_delete_params.CallDeleteParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallDeleteResponse,
        )

    async def end(
        self,
        *,
        end: call_end_params.End,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Call End

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/call/end",
            body=await async_maybe_transform({"end": end}, call_end_params.CallEndParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def query_stats(
        self,
        *,
        project_id: str,
        expand_columns: Optional[SequenceNotStr[str]] | Omit = omit,
        filter: Optional[call_query_stats_params.Filter] | Omit = omit,
        include_total_storage_size: Optional[bool] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        query: Optional[call_query_stats_params.Query] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallQueryStatsResponse:
        """
        Calls Query Stats

        Args:
          expand_columns: Columns with refs to objects or table rows that require expansion during
              filtering or ordering.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/calls/query_stats",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "expand_columns": expand_columns,
                    "filter": filter,
                    "include_total_storage_size": include_total_storage_size,
                    "limit": limit,
                    "query": query,
                },
                call_query_stats_params.CallQueryStatsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallQueryStatsResponse,
        )

    async def read(
        self,
        *,
        id: str,
        project_id: str,
        include_costs: Optional[bool] | Omit = omit,
        include_storage_size: Optional[bool] | Omit = omit,
        include_total_storage_size: Optional[bool] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallReadResponse:
        """
        Call Read

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/call/read",
            body=await async_maybe_transform(
                {
                    "id": id,
                    "project_id": project_id,
                    "include_costs": include_costs,
                    "include_storage_size": include_storage_size,
                    "include_total_storage_size": include_total_storage_size,
                },
                call_read_params.CallReadParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallReadResponse,
        )

    async def start(
        self,
        *,
        start: call_start_params.Start,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallStartResponse:
        """
        Call Start

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/call/start",
            body=await async_maybe_transform({"start": start}, call_start_params.CallStartParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallStartResponse,
        )

    async def stream_query(
        self,
        *,
        project_id: str,
        columns: Optional[SequenceNotStr[str]] | Omit = omit,
        expand_columns: Optional[SequenceNotStr[str]] | Omit = omit,
        filter: Optional[call_stream_query_params.Filter] | Omit = omit,
        include_costs: Optional[bool] | Omit = omit,
        include_feedback: Optional[bool] | Omit = omit,
        include_storage_size: Optional[bool] | Omit = omit,
        include_total_storage_size: Optional[bool] | Omit = omit,
        include_usernames: Optional[bool] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        query: Optional[call_stream_query_params.Query] | Omit = omit,
        return_expanded_column_values: Optional[bool] | Omit = omit,
        sort_by: Optional[Iterable[call_stream_query_params.SortBy]] | Omit = omit,
        accept: str | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncJSONLDecoder[object]:
        """Calls Query Stream

        Args:
          expand_columns: Columns to expand, i.e.

        refs to other objects

          include_costs: Beta, subject to change. If true, the response will include any model costs for
              each call.

          include_feedback: Beta, subject to change. If true, the response will include feedback for each
              call.

          include_storage_size: Beta, subject to change. If true, the response will include the storage size for
              a call.

          include_total_storage_size: Beta, subject to change. If true, the response will include the total storage
              size for a trace.

          include_usernames: If true, the response will attempt to resolve each call's wb_user_id to a
              username for the duration of this request.

          return_expanded_column_values: If true, the response will include raw values for expanded columns. If false,
              the response expand_columns will only be used for filtering and ordering. This
              is useful for clients that want to resolve refs themselves, e.g. for performance
              reasons.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        extra_headers = {"Accept": "application/jsonl", **(extra_headers or {})}
        extra_headers = {**strip_not_given({"accept": accept}), **(extra_headers or {})}
        return await self._post(
            "/calls/stream_query",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "columns": columns,
                    "expand_columns": expand_columns,
                    "filter": filter,
                    "include_costs": include_costs,
                    "include_feedback": include_feedback,
                    "include_storage_size": include_storage_size,
                    "include_total_storage_size": include_total_storage_size,
                    "include_usernames": include_usernames,
                    "limit": limit,
                    "offset": offset,
                    "query": query,
                    "return_expanded_column_values": return_expanded_column_values,
                    "sort_by": sort_by,
                },
                call_stream_query_params.CallStreamQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AsyncJSONLDecoder[object],
            stream=True,
        )

    async def upsert_batch(
        self,
        *,
        batch: Iterable[call_upsert_batch_params.Batch],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallUpsertBatchResponse:
        """
        Call Start Batch

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/call/upsert_batch",
            body=await async_maybe_transform({"batch": batch}, call_upsert_batch_params.CallUpsertBatchParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallUpsertBatchResponse,
        )

    async def usage(
        self,
        *,
        call_ids: SequenceNotStr[str],
        project_id: str,
        include_costs: bool | Omit = omit,
        limit: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CallUsageResponse:
        """
        Compute aggregated usage for multiple root calls, with descendant rollup.

        Args:
          call_ids: Root call IDs to aggregate. Each result key corresponds to one input call ID.

          include_costs: If true, include cost calculations in the usage.

          limit: Maximum number of calls to process across all traces. Acts as a safety limit to
              prevent unbounded memory usage.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/calls/usage",
            body=await async_maybe_transform(
                {
                    "call_ids": call_ids,
                    "project_id": project_id,
                    "include_costs": include_costs,
                    "limit": limit,
                },
                call_usage_params.CallUsageParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CallUsageResponse,
        )


class CallsResourceWithRawResponse:
    def __init__(self, calls: CallsResource) -> None:
        self._calls = calls

        self.update = to_raw_response_wrapper(
            calls.update,
        )
        self.delete = to_raw_response_wrapper(
            calls.delete,
        )
        self.end = to_raw_response_wrapper(
            calls.end,
        )
        self.query_stats = to_raw_response_wrapper(
            calls.query_stats,
        )
        self.read = to_raw_response_wrapper(
            calls.read,
        )
        self.start = to_raw_response_wrapper(
            calls.start,
        )
        self.stream_query = to_raw_response_wrapper(
            calls.stream_query,
        )
        self.upsert_batch = to_raw_response_wrapper(
            calls.upsert_batch,
        )
        self.usage = to_raw_response_wrapper(
            calls.usage,
        )


class AsyncCallsResourceWithRawResponse:
    def __init__(self, calls: AsyncCallsResource) -> None:
        self._calls = calls

        self.update = async_to_raw_response_wrapper(
            calls.update,
        )
        self.delete = async_to_raw_response_wrapper(
            calls.delete,
        )
        self.end = async_to_raw_response_wrapper(
            calls.end,
        )
        self.query_stats = async_to_raw_response_wrapper(
            calls.query_stats,
        )
        self.read = async_to_raw_response_wrapper(
            calls.read,
        )
        self.start = async_to_raw_response_wrapper(
            calls.start,
        )
        self.stream_query = async_to_raw_response_wrapper(
            calls.stream_query,
        )
        self.upsert_batch = async_to_raw_response_wrapper(
            calls.upsert_batch,
        )
        self.usage = async_to_raw_response_wrapper(
            calls.usage,
        )


class CallsResourceWithStreamingResponse:
    def __init__(self, calls: CallsResource) -> None:
        self._calls = calls

        self.update = to_streamed_response_wrapper(
            calls.update,
        )
        self.delete = to_streamed_response_wrapper(
            calls.delete,
        )
        self.end = to_streamed_response_wrapper(
            calls.end,
        )
        self.query_stats = to_streamed_response_wrapper(
            calls.query_stats,
        )
        self.read = to_streamed_response_wrapper(
            calls.read,
        )
        self.start = to_streamed_response_wrapper(
            calls.start,
        )
        self.stream_query = to_streamed_response_wrapper(
            calls.stream_query,
        )
        self.upsert_batch = to_streamed_response_wrapper(
            calls.upsert_batch,
        )
        self.usage = to_streamed_response_wrapper(
            calls.usage,
        )


class AsyncCallsResourceWithStreamingResponse:
    def __init__(self, calls: AsyncCallsResource) -> None:
        self._calls = calls

        self.update = async_to_streamed_response_wrapper(
            calls.update,
        )
        self.delete = async_to_streamed_response_wrapper(
            calls.delete,
        )
        self.end = async_to_streamed_response_wrapper(
            calls.end,
        )
        self.query_stats = async_to_streamed_response_wrapper(
            calls.query_stats,
        )
        self.read = async_to_streamed_response_wrapper(
            calls.read,
        )
        self.start = async_to_streamed_response_wrapper(
            calls.start,
        )
        self.stream_query = async_to_streamed_response_wrapper(
            calls.stream_query,
        )
        self.upsert_batch = async_to_streamed_response_wrapper(
            calls.upsert_batch,
        )
        self.usage = async_to_streamed_response_wrapper(
            calls.usage,
        )
