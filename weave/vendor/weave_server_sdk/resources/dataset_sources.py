# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Iterable, Optional
from typing_extensions import Literal

import httpx

from ..types import dataset_source_link_params, dataset_source_query_params, dataset_source_source_datasets_query_params
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
from ..types.dataset_source_link_response import DatasetSourceLinkResponse
from ..types.dataset_source_query_response import DatasetSourceQueryResponse
from ..types.dataset_source_source_datasets_query_response import DatasetSourceSourceDatasetsQueryResponse

__all__ = ["DatasetSourcesResource", "AsyncDatasetSourcesResource"]


class DatasetSourcesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> DatasetSourcesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return DatasetSourcesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> DatasetSourcesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return DatasetSourcesResourceWithStreamingResponse(self)

    def link(
        self,
        *,
        dataset_digest: str,
        dataset_object_id: str,
        links: Iterable[dataset_source_link_params.Link],
        project_id: str,
        include_created_status: bool | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetSourceLinkResponse:
        """
        Link source calls/spans to dataset rows (batch, idempotent).

        Args:
          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/dataset_sources/link",
            body=maybe_transform(
                {
                    "dataset_digest": dataset_digest,
                    "dataset_object_id": dataset_object_id,
                    "links": links,
                    "project_id": project_id,
                    "include_created_status": include_created_status,
                    "wb_user_id": wb_user_id,
                },
                dataset_source_link_params.DatasetSourceLinkParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetSourceLinkResponse,
        )

    def query(
        self,
        *,
        dataset_object_id: str,
        project_id: str,
        include_deleted: bool | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        row_digests: Optional[SequenceNotStr[str]] | Omit = omit,
        source_kinds: Optional[List[Literal["call", "span", "conversation"]]] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetSourceQueryResponse:
        """
        Forward provenance lookup: dataset (+ optional row digests) -> sources.

        Args:
          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/dataset_sources/query",
            body=maybe_transform(
                {
                    "dataset_object_id": dataset_object_id,
                    "project_id": project_id,
                    "include_deleted": include_deleted,
                    "limit": limit,
                    "offset": offset,
                    "row_digests": row_digests,
                    "source_kinds": source_kinds,
                    "wb_user_id": wb_user_id,
                },
                dataset_source_query_params.DatasetSourceQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetSourceQueryResponse,
        )

    def source_datasets_query(
        self,
        *,
        project_id: str,
        sources: Iterable[dataset_source_source_datasets_query_params.Source],
        include_deleted: bool | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetSourceSourceDatasetsQueryResponse:
        """
        Reverse provenance lookup: sources -> datasets they appear in.

        Args:
          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/dataset_sources/source_datasets_query",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "sources": sources,
                    "include_deleted": include_deleted,
                    "wb_user_id": wb_user_id,
                },
                dataset_source_source_datasets_query_params.DatasetSourceSourceDatasetsQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetSourceSourceDatasetsQueryResponse,
        )


class AsyncDatasetSourcesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncDatasetSourcesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncDatasetSourcesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncDatasetSourcesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncDatasetSourcesResourceWithStreamingResponse(self)

    async def link(
        self,
        *,
        dataset_digest: str,
        dataset_object_id: str,
        links: Iterable[dataset_source_link_params.Link],
        project_id: str,
        include_created_status: bool | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetSourceLinkResponse:
        """
        Link source calls/spans to dataset rows (batch, idempotent).

        Args:
          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/dataset_sources/link",
            body=await async_maybe_transform(
                {
                    "dataset_digest": dataset_digest,
                    "dataset_object_id": dataset_object_id,
                    "links": links,
                    "project_id": project_id,
                    "include_created_status": include_created_status,
                    "wb_user_id": wb_user_id,
                },
                dataset_source_link_params.DatasetSourceLinkParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetSourceLinkResponse,
        )

    async def query(
        self,
        *,
        dataset_object_id: str,
        project_id: str,
        include_deleted: bool | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        row_digests: Optional[SequenceNotStr[str]] | Omit = omit,
        source_kinds: Optional[List[Literal["call", "span", "conversation"]]] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetSourceQueryResponse:
        """
        Forward provenance lookup: dataset (+ optional row digests) -> sources.

        Args:
          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/dataset_sources/query",
            body=await async_maybe_transform(
                {
                    "dataset_object_id": dataset_object_id,
                    "project_id": project_id,
                    "include_deleted": include_deleted,
                    "limit": limit,
                    "offset": offset,
                    "row_digests": row_digests,
                    "source_kinds": source_kinds,
                    "wb_user_id": wb_user_id,
                },
                dataset_source_query_params.DatasetSourceQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetSourceQueryResponse,
        )

    async def source_datasets_query(
        self,
        *,
        project_id: str,
        sources: Iterable[dataset_source_source_datasets_query_params.Source],
        include_deleted: bool | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> DatasetSourceSourceDatasetsQueryResponse:
        """
        Reverse provenance lookup: sources -> datasets they appear in.

        Args:
          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/dataset_sources/source_datasets_query",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "sources": sources,
                    "include_deleted": include_deleted,
                    "wb_user_id": wb_user_id,
                },
                dataset_source_source_datasets_query_params.DatasetSourceSourceDatasetsQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=DatasetSourceSourceDatasetsQueryResponse,
        )


class DatasetSourcesResourceWithRawResponse:
    def __init__(self, dataset_sources: DatasetSourcesResource) -> None:
        self._dataset_sources = dataset_sources

        self.link = to_raw_response_wrapper(
            dataset_sources.link,
        )
        self.query = to_raw_response_wrapper(
            dataset_sources.query,
        )
        self.source_datasets_query = to_raw_response_wrapper(
            dataset_sources.source_datasets_query,
        )


class AsyncDatasetSourcesResourceWithRawResponse:
    def __init__(self, dataset_sources: AsyncDatasetSourcesResource) -> None:
        self._dataset_sources = dataset_sources

        self.link = async_to_raw_response_wrapper(
            dataset_sources.link,
        )
        self.query = async_to_raw_response_wrapper(
            dataset_sources.query,
        )
        self.source_datasets_query = async_to_raw_response_wrapper(
            dataset_sources.source_datasets_query,
        )


class DatasetSourcesResourceWithStreamingResponse:
    def __init__(self, dataset_sources: DatasetSourcesResource) -> None:
        self._dataset_sources = dataset_sources

        self.link = to_streamed_response_wrapper(
            dataset_sources.link,
        )
        self.query = to_streamed_response_wrapper(
            dataset_sources.query,
        )
        self.source_datasets_query = to_streamed_response_wrapper(
            dataset_sources.source_datasets_query,
        )


class AsyncDatasetSourcesResourceWithStreamingResponse:
    def __init__(self, dataset_sources: AsyncDatasetSourcesResource) -> None:
        self._dataset_sources = dataset_sources

        self.link = async_to_streamed_response_wrapper(
            dataset_sources.link,
        )
        self.query = async_to_streamed_response_wrapper(
            dataset_sources.query,
        )
        self.source_datasets_query = async_to_streamed_response_wrapper(
            dataset_sources.source_datasets_query,
        )
