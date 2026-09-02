# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
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
from ...types.annotation_queues import item_add_params, item_query_params, item_update_progress_params
from ...types.annotation_queues.item_add_response import ItemAddResponse
from ...types.annotation_queues.item_query_response import ItemQueryResponse
from ...types.annotation_queues.item_update_progress_response import ItemUpdateProgressResponse

__all__ = ["ItemsResource", "AsyncItemsResource"]


class ItemsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ItemsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return ItemsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ItemsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return ItemsResourceWithStreamingResponse(self)

    def add(
        self,
        queue_id: str,
        *,
        call_ids: SequenceNotStr[str],
        display_fields: SequenceNotStr[str],
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemAddResponse:
        """
        Add calls to an annotation queue.

        Args:
          display_fields: JSON paths to display to annotators

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._post(
            path_template("/annotation_queues/{queue_id}/items", queue_id=queue_id),
            body=maybe_transform(
                {
                    "call_ids": call_ids,
                    "display_fields": display_fields,
                    "project_id": project_id,
                },
                item_add_params.ItemAddParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemAddResponse,
        )

    def query(
        self,
        queue_id: str,
        *,
        project_id: str,
        filter: Optional[item_query_params.Filter] | Omit = omit,
        include_position: bool | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        sort_by: Optional[Iterable[item_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemQueryResponse:
        """
        Query items in an annotation queue with pagination and sorting.

        Args:
          filter: Simple filter for annotation queue items.

              Supports equality filtering on call metadata fields and IN filtering on
              annotation state.

          include_position: Include position_in_queue field (1-based index in full queue)

          sort_by: Sort by multiple fields (e.g., created_at, updated_at)

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return self._post(
            path_template("/annotation_queues/{queue_id}/items/query", queue_id=queue_id),
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "filter": filter,
                    "include_position": include_position,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                item_query_params.ItemQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemQueryResponse,
        )

    def update_progress(
        self,
        item_id: str,
        *,
        queue_id: str,
        annotation_state: str,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemUpdateProgressResponse:
        """
        Update the annotation state of a queue item for the current annotator.

        Args:
          annotation_state: New state: 'in_progress', 'completed', or 'skipped'

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        if not item_id:
            raise ValueError(f"Expected a non-empty value for `item_id` but received {item_id!r}")
        return self._post(
            path_template("/annotation_queues/{queue_id}/items/{item_id}/progress", queue_id=queue_id, item_id=item_id),
            body=maybe_transform(
                {
                    "annotation_state": annotation_state,
                    "project_id": project_id,
                },
                item_update_progress_params.ItemUpdateProgressParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemUpdateProgressResponse,
        )


class AsyncItemsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncItemsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncItemsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncItemsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncItemsResourceWithStreamingResponse(self)

    async def add(
        self,
        queue_id: str,
        *,
        call_ids: SequenceNotStr[str],
        display_fields: SequenceNotStr[str],
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemAddResponse:
        """
        Add calls to an annotation queue.

        Args:
          display_fields: JSON paths to display to annotators

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._post(
            path_template("/annotation_queues/{queue_id}/items", queue_id=queue_id),
            body=await async_maybe_transform(
                {
                    "call_ids": call_ids,
                    "display_fields": display_fields,
                    "project_id": project_id,
                },
                item_add_params.ItemAddParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemAddResponse,
        )

    async def query(
        self,
        queue_id: str,
        *,
        project_id: str,
        filter: Optional[item_query_params.Filter] | Omit = omit,
        include_position: bool | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        sort_by: Optional[Iterable[item_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemQueryResponse:
        """
        Query items in an annotation queue with pagination and sorting.

        Args:
          filter: Simple filter for annotation queue items.

              Supports equality filtering on call metadata fields and IN filtering on
              annotation state.

          include_position: Include position_in_queue field (1-based index in full queue)

          sort_by: Sort by multiple fields (e.g., created_at, updated_at)

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        return await self._post(
            path_template("/annotation_queues/{queue_id}/items/query", queue_id=queue_id),
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "filter": filter,
                    "include_position": include_position,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                item_query_params.ItemQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemQueryResponse,
        )

    async def update_progress(
        self,
        item_id: str,
        *,
        queue_id: str,
        annotation_state: str,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ItemUpdateProgressResponse:
        """
        Update the annotation state of a queue item for the current annotator.

        Args:
          annotation_state: New state: 'in_progress', 'completed', or 'skipped'

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not queue_id:
            raise ValueError(f"Expected a non-empty value for `queue_id` but received {queue_id!r}")
        if not item_id:
            raise ValueError(f"Expected a non-empty value for `item_id` but received {item_id!r}")
        return await self._post(
            path_template("/annotation_queues/{queue_id}/items/{item_id}/progress", queue_id=queue_id, item_id=item_id),
            body=await async_maybe_transform(
                {
                    "annotation_state": annotation_state,
                    "project_id": project_id,
                },
                item_update_progress_params.ItemUpdateProgressParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ItemUpdateProgressResponse,
        )


class ItemsResourceWithRawResponse:
    def __init__(self, items: ItemsResource) -> None:
        self._items = items

        self.add = to_raw_response_wrapper(
            items.add,
        )
        self.query = to_raw_response_wrapper(
            items.query,
        )
        self.update_progress = to_raw_response_wrapper(
            items.update_progress,
        )


class AsyncItemsResourceWithRawResponse:
    def __init__(self, items: AsyncItemsResource) -> None:
        self._items = items

        self.add = async_to_raw_response_wrapper(
            items.add,
        )
        self.query = async_to_raw_response_wrapper(
            items.query,
        )
        self.update_progress = async_to_raw_response_wrapper(
            items.update_progress,
        )


class ItemsResourceWithStreamingResponse:
    def __init__(self, items: ItemsResource) -> None:
        self._items = items

        self.add = to_streamed_response_wrapper(
            items.add,
        )
        self.query = to_streamed_response_wrapper(
            items.query,
        )
        self.update_progress = to_streamed_response_wrapper(
            items.update_progress,
        )


class AsyncItemsResourceWithStreamingResponse:
    def __init__(self, items: AsyncItemsResource) -> None:
        self._items = items

        self.add = async_to_streamed_response_wrapper(
            items.add,
        )
        self.query = async_to_streamed_response_wrapper(
            items.query,
        )
        self.update_progress = async_to_streamed_response_wrapper(
            items.update_progress,
        )
