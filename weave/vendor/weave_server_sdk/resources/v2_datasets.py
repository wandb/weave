# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional

import httpx

from ..types import v2_dataset_list_params, v2_dataset_create_params, v2_dataset_delete_params
from .._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
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
from ..types.v2_dataset_read_response import V2DatasetReadResponse
from ..types.v2_dataset_create_response import V2DatasetCreateResponse
from ..types.v2_dataset_delete_response import V2DatasetDeleteResponse

__all__ = ["V2DatasetsResource", "AsyncV2DatasetsResource"]


class V2DatasetsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> V2DatasetsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return V2DatasetsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> V2DatasetsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return V2DatasetsResourceWithStreamingResponse(self)

    def create(
        self,
        project: str,
        *,
        entity: str,
        rows: Iterable[Dict[str, object]],
        description: Optional[str] | Omit = omit,
        name: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2DatasetCreateResponse:
        """
        Create a dataset object.

        Args:
          rows: Dataset rows

          description: A description of this dataset

          name: The name of this dataset. Datasets with the same name will be versioned
              together.

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
            path_template("/v2/{entity}/{project}/datasets", entity=entity, project=project),
            body=maybe_transform(
                {
                    "rows": rows,
                    "description": description,
                    "name": name,
                },
                v2_dataset_create_params.V2DatasetCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2DatasetCreateResponse,
        )

    def list(
        self,
        project: str,
        *,
        entity: str,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        List dataset objects.

        Args:
          limit: Maximum number of datasets to return

          offset: Number of datasets to skip

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        return self._get(
            path_template("/v2/{entity}/{project}/datasets", entity=entity, project=project),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "limit": limit,
                        "offset": offset,
                    },
                    v2_dataset_list_params.V2DatasetListParams,
                ),
            ),
            cast_to=object,
        )

    def delete(
        self,
        object_id: str,
        *,
        entity: str,
        project: str,
        digests: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2DatasetDeleteResponse:
        """Delete a dataset object.

        If digests are provided, only those versions are
        deleted. Otherwise, all versions are deleted.

        Args:
          digests: List of digests to delete. If not provided, all digests for the dataset will be
              deleted.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        if not object_id:
            raise ValueError(f"Expected a non-empty value for `object_id` but received {object_id!r}")
        return self._delete(
            path_template(
                "/v2/{entity}/{project}/datasets/{object_id}", entity=entity, project=project, object_id=object_id
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"digests": digests}, v2_dataset_delete_params.V2DatasetDeleteParams),
            ),
            cast_to=V2DatasetDeleteResponse,
        )

    def read(
        self,
        digest: str,
        *,
        entity: str,
        project: str,
        object_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2DatasetReadResponse:
        """
        Get a dataset object.

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
        if not object_id:
            raise ValueError(f"Expected a non-empty value for `object_id` but received {object_id!r}")
        if not digest:
            raise ValueError(f"Expected a non-empty value for `digest` but received {digest!r}")
        return self._get(
            path_template(
                "/v2/{entity}/{project}/datasets/{object_id}/versions/{digest}",
                entity=entity,
                project=project,
                object_id=object_id,
                digest=digest,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2DatasetReadResponse,
        )


class AsyncV2DatasetsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncV2DatasetsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncV2DatasetsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncV2DatasetsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncV2DatasetsResourceWithStreamingResponse(self)

    async def create(
        self,
        project: str,
        *,
        entity: str,
        rows: Iterable[Dict[str, object]],
        description: Optional[str] | Omit = omit,
        name: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2DatasetCreateResponse:
        """
        Create a dataset object.

        Args:
          rows: Dataset rows

          description: A description of this dataset

          name: The name of this dataset. Datasets with the same name will be versioned
              together.

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
            path_template("/v2/{entity}/{project}/datasets", entity=entity, project=project),
            body=await async_maybe_transform(
                {
                    "rows": rows,
                    "description": description,
                    "name": name,
                },
                v2_dataset_create_params.V2DatasetCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2DatasetCreateResponse,
        )

    async def list(
        self,
        project: str,
        *,
        entity: str,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        List dataset objects.

        Args:
          limit: Maximum number of datasets to return

          offset: Number of datasets to skip

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        return await self._get(
            path_template("/v2/{entity}/{project}/datasets", entity=entity, project=project),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "limit": limit,
                        "offset": offset,
                    },
                    v2_dataset_list_params.V2DatasetListParams,
                ),
            ),
            cast_to=object,
        )

    async def delete(
        self,
        object_id: str,
        *,
        entity: str,
        project: str,
        digests: Optional[SequenceNotStr[str]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2DatasetDeleteResponse:
        """Delete a dataset object.

        If digests are provided, only those versions are
        deleted. Otherwise, all versions are deleted.

        Args:
          digests: List of digests to delete. If not provided, all digests for the dataset will be
              deleted.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        if not object_id:
            raise ValueError(f"Expected a non-empty value for `object_id` but received {object_id!r}")
        return await self._delete(
            path_template(
                "/v2/{entity}/{project}/datasets/{object_id}", entity=entity, project=project, object_id=object_id
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"digests": digests}, v2_dataset_delete_params.V2DatasetDeleteParams),
            ),
            cast_to=V2DatasetDeleteResponse,
        )

    async def read(
        self,
        digest: str,
        *,
        entity: str,
        project: str,
        object_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2DatasetReadResponse:
        """
        Get a dataset object.

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
        if not object_id:
            raise ValueError(f"Expected a non-empty value for `object_id` but received {object_id!r}")
        if not digest:
            raise ValueError(f"Expected a non-empty value for `digest` but received {digest!r}")
        return await self._get(
            path_template(
                "/v2/{entity}/{project}/datasets/{object_id}/versions/{digest}",
                entity=entity,
                project=project,
                object_id=object_id,
                digest=digest,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2DatasetReadResponse,
        )


class V2DatasetsResourceWithRawResponse:
    def __init__(self, v2_datasets: V2DatasetsResource) -> None:
        self._v2_datasets = v2_datasets

        self.create = to_raw_response_wrapper(
            v2_datasets.create,
        )
        self.list = to_raw_response_wrapper(
            v2_datasets.list,
        )
        self.delete = to_raw_response_wrapper(
            v2_datasets.delete,
        )
        self.read = to_raw_response_wrapper(
            v2_datasets.read,
        )


class AsyncV2DatasetsResourceWithRawResponse:
    def __init__(self, v2_datasets: AsyncV2DatasetsResource) -> None:
        self._v2_datasets = v2_datasets

        self.create = async_to_raw_response_wrapper(
            v2_datasets.create,
        )
        self.list = async_to_raw_response_wrapper(
            v2_datasets.list,
        )
        self.delete = async_to_raw_response_wrapper(
            v2_datasets.delete,
        )
        self.read = async_to_raw_response_wrapper(
            v2_datasets.read,
        )


class V2DatasetsResourceWithStreamingResponse:
    def __init__(self, v2_datasets: V2DatasetsResource) -> None:
        self._v2_datasets = v2_datasets

        self.create = to_streamed_response_wrapper(
            v2_datasets.create,
        )
        self.list = to_streamed_response_wrapper(
            v2_datasets.list,
        )
        self.delete = to_streamed_response_wrapper(
            v2_datasets.delete,
        )
        self.read = to_streamed_response_wrapper(
            v2_datasets.read,
        )


class AsyncV2DatasetsResourceWithStreamingResponse:
    def __init__(self, v2_datasets: AsyncV2DatasetsResource) -> None:
        self._v2_datasets = v2_datasets

        self.create = async_to_streamed_response_wrapper(
            v2_datasets.create,
        )
        self.list = async_to_streamed_response_wrapper(
            v2_datasets.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            v2_datasets.delete,
        )
        self.read = async_to_streamed_response_wrapper(
            v2_datasets.read,
        )
