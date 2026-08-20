# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional

import httpx

from ..types import (
    table_query_params,
    table_create_params,
    table_update_params,
    table_query_stats_params,
    table_query_stats_batch_params,
    table_create_from_digests_params,
)
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
from ..types.table_query_response import TableQueryResponse
from ..types.table_create_response import TableCreateResponse
from ..types.table_update_response import TableUpdateResponse
from ..types.table_query_stats_response import TableQueryStatsResponse
from ..types.table_query_stats_batch_response import TableQueryStatsBatchResponse
from ..types.table_create_from_digests_response import TableCreateFromDigestsResponse

__all__ = ["TablesResource", "AsyncTablesResource"]


class TablesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> TablesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return TablesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> TablesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return TablesResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        table: table_create_params.Table,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableCreateResponse:
        """
        Table Create

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/table/create",
            body=maybe_transform({"table": table}, table_create_params.TableCreateParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableCreateResponse,
        )

    def update(
        self,
        *,
        base_digest: str,
        project_id: str,
        updates: Iterable[table_update_params.Update],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableUpdateResponse:
        """
        Table Update

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/table/update",
            body=maybe_transform(
                {
                    "base_digest": base_digest,
                    "project_id": project_id,
                    "updates": updates,
                },
                table_update_params.TableUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableUpdateResponse,
        )

    def create_from_digests(
        self,
        *,
        project_id: str,
        row_digests: SequenceNotStr[str],
        expected_digest: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableCreateFromDigestsResponse:
        """
        Table Create From Digests

        Args:
          expected_digest: Client-computed table digest for server-side validation.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/table/create_from_digests",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "row_digests": row_digests,
                    "expected_digest": expected_digest,
                },
                table_create_from_digests_params.TableCreateFromDigestsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableCreateFromDigestsResponse,
        )

    def query(
        self,
        *,
        digest: str,
        project_id: str,
        filter: Optional[table_query_params.Filter] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        sort_by: Optional[Iterable[table_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableQueryResponse:
        """
        Table Query

        Args:
          digest: The digest of the table to query

          project_id: The ID of the project

          filter: Optional filter to apply to the query. See `TableRowFilter` for more details.

          limit: Maximum number of rows to return

          offset: Number of rows to skip before starting to return rows

          sort_by: List of fields to sort by. Fields can be dot-separated to access dictionary
              values. No sorting uses the default table order (insertion order).

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/table/query",
            body=maybe_transform(
                {
                    "digest": digest,
                    "project_id": project_id,
                    "filter": filter,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                table_query_params.TableQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableQueryResponse,
        )

    def query_stats(
        self,
        *,
        digest: str,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableQueryStatsResponse:
        """
        Table Query Stats

        Args:
          digest: The digest of the table to query

          project_id: The ID of the project

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/table/query_stats",
            body=maybe_transform(
                {
                    "digest": digest,
                    "project_id": project_id,
                },
                table_query_stats_params.TableQueryStatsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableQueryStatsResponse,
        )

    def query_stats_batch(
        self,
        *,
        project_id: str,
        digests: Optional[SequenceNotStr[str]] | Omit = omit,
        include_storage_size: Optional[bool] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableQueryStatsBatchResponse:
        """
        Table Query Stats Batch

        Args:
          project_id: The ID of the project

          digests: The digests of the tables to query

          include_storage_size: If true, the `storage_size_bytes` column is returned.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/table/query_stats_batch",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "digests": digests,
                    "include_storage_size": include_storage_size,
                },
                table_query_stats_batch_params.TableQueryStatsBatchParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableQueryStatsBatchResponse,
        )


class AsyncTablesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncTablesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncTablesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncTablesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncTablesResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        table: table_create_params.Table,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableCreateResponse:
        """
        Table Create

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/table/create",
            body=await async_maybe_transform({"table": table}, table_create_params.TableCreateParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableCreateResponse,
        )

    async def update(
        self,
        *,
        base_digest: str,
        project_id: str,
        updates: Iterable[table_update_params.Update],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableUpdateResponse:
        """
        Table Update

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/table/update",
            body=await async_maybe_transform(
                {
                    "base_digest": base_digest,
                    "project_id": project_id,
                    "updates": updates,
                },
                table_update_params.TableUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableUpdateResponse,
        )

    async def create_from_digests(
        self,
        *,
        project_id: str,
        row_digests: SequenceNotStr[str],
        expected_digest: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableCreateFromDigestsResponse:
        """
        Table Create From Digests

        Args:
          expected_digest: Client-computed table digest for server-side validation.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/table/create_from_digests",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "row_digests": row_digests,
                    "expected_digest": expected_digest,
                },
                table_create_from_digests_params.TableCreateFromDigestsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableCreateFromDigestsResponse,
        )

    async def query(
        self,
        *,
        digest: str,
        project_id: str,
        filter: Optional[table_query_params.Filter] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        sort_by: Optional[Iterable[table_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableQueryResponse:
        """
        Table Query

        Args:
          digest: The digest of the table to query

          project_id: The ID of the project

          filter: Optional filter to apply to the query. See `TableRowFilter` for more details.

          limit: Maximum number of rows to return

          offset: Number of rows to skip before starting to return rows

          sort_by: List of fields to sort by. Fields can be dot-separated to access dictionary
              values. No sorting uses the default table order (insertion order).

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/table/query",
            body=await async_maybe_transform(
                {
                    "digest": digest,
                    "project_id": project_id,
                    "filter": filter,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                table_query_params.TableQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableQueryResponse,
        )

    async def query_stats(
        self,
        *,
        digest: str,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableQueryStatsResponse:
        """
        Table Query Stats

        Args:
          digest: The digest of the table to query

          project_id: The ID of the project

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/table/query_stats",
            body=await async_maybe_transform(
                {
                    "digest": digest,
                    "project_id": project_id,
                },
                table_query_stats_params.TableQueryStatsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableQueryStatsResponse,
        )

    async def query_stats_batch(
        self,
        *,
        project_id: str,
        digests: Optional[SequenceNotStr[str]] | Omit = omit,
        include_storage_size: Optional[bool] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TableQueryStatsBatchResponse:
        """
        Table Query Stats Batch

        Args:
          project_id: The ID of the project

          digests: The digests of the tables to query

          include_storage_size: If true, the `storage_size_bytes` column is returned.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/table/query_stats_batch",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "digests": digests,
                    "include_storage_size": include_storage_size,
                },
                table_query_stats_batch_params.TableQueryStatsBatchParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TableQueryStatsBatchResponse,
        )


class TablesResourceWithRawResponse:
    def __init__(self, tables: TablesResource) -> None:
        self._tables = tables

        self.create = to_raw_response_wrapper(
            tables.create,
        )
        self.update = to_raw_response_wrapper(
            tables.update,
        )
        self.create_from_digests = to_raw_response_wrapper(
            tables.create_from_digests,
        )
        self.query = to_raw_response_wrapper(
            tables.query,
        )
        self.query_stats = to_raw_response_wrapper(
            tables.query_stats,
        )
        self.query_stats_batch = to_raw_response_wrapper(
            tables.query_stats_batch,
        )


class AsyncTablesResourceWithRawResponse:
    def __init__(self, tables: AsyncTablesResource) -> None:
        self._tables = tables

        self.create = async_to_raw_response_wrapper(
            tables.create,
        )
        self.update = async_to_raw_response_wrapper(
            tables.update,
        )
        self.create_from_digests = async_to_raw_response_wrapper(
            tables.create_from_digests,
        )
        self.query = async_to_raw_response_wrapper(
            tables.query,
        )
        self.query_stats = async_to_raw_response_wrapper(
            tables.query_stats,
        )
        self.query_stats_batch = async_to_raw_response_wrapper(
            tables.query_stats_batch,
        )


class TablesResourceWithStreamingResponse:
    def __init__(self, tables: TablesResource) -> None:
        self._tables = tables

        self.create = to_streamed_response_wrapper(
            tables.create,
        )
        self.update = to_streamed_response_wrapper(
            tables.update,
        )
        self.create_from_digests = to_streamed_response_wrapper(
            tables.create_from_digests,
        )
        self.query = to_streamed_response_wrapper(
            tables.query,
        )
        self.query_stats = to_streamed_response_wrapper(
            tables.query_stats,
        )
        self.query_stats_batch = to_streamed_response_wrapper(
            tables.query_stats_batch,
        )


class AsyncTablesResourceWithStreamingResponse:
    def __init__(self, tables: AsyncTablesResource) -> None:
        self._tables = tables

        self.create = async_to_streamed_response_wrapper(
            tables.create,
        )
        self.update = async_to_streamed_response_wrapper(
            tables.update,
        )
        self.create_from_digests = async_to_streamed_response_wrapper(
            tables.create_from_digests,
        )
        self.query = async_to_streamed_response_wrapper(
            tables.query,
        )
        self.query_stats = async_to_streamed_response_wrapper(
            tables.query_stats,
        )
        self.query_stats_batch = async_to_streamed_response_wrapper(
            tables.query_stats_batch,
        )
