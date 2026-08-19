# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional

import httpx

from ..types import v2_model_list_params, v2_model_create_params, v2_model_delete_params
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
from ..types.v2_model_read_response import V2ModelReadResponse
from ..types.v2_model_create_response import V2ModelCreateResponse
from ..types.v2_model_delete_response import V2ModelDeleteResponse

__all__ = ["V2ModelsResource", "AsyncV2ModelsResource"]


class V2ModelsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> V2ModelsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return V2ModelsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> V2ModelsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return V2ModelsResourceWithStreamingResponse(self)

    def create(
        self,
        project: str,
        *,
        entity: str,
        name: str,
        source_code: str,
        attributes: Optional[Dict[str, object]] | Omit = omit,
        description: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2ModelCreateResponse:
        """Create a model object.

        Args:
          name: The name of this model.

        Models with the same name will be versioned together.

          source_code: Complete source code for the Model class including imports

          attributes: Additional attributes to be stored with the model

          description: A description of this model

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
            path_template("/v2/{entity}/{project}/models", entity=entity, project=project),
            body=maybe_transform(
                {
                    "name": name,
                    "source_code": source_code,
                    "attributes": attributes,
                    "description": description,
                },
                v2_model_create_params.V2ModelCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2ModelCreateResponse,
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
        List model objects.

        Args:
          limit: Maximum number of models to return

          offset: Number of models to skip

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
            path_template("/v2/{entity}/{project}/models", entity=entity, project=project),
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
                    v2_model_list_params.V2ModelListParams,
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
    ) -> V2ModelDeleteResponse:
        """Delete a model object.

        If digests are provided, only those versions are deleted.
        Otherwise, all versions are deleted.

        Args:
          digests: List of digests to delete. If not provided, all digests for the model will be
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
                "/v2/{entity}/{project}/models/{object_id}", entity=entity, project=project, object_id=object_id
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"digests": digests}, v2_model_delete_params.V2ModelDeleteParams),
            ),
            cast_to=V2ModelDeleteResponse,
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
    ) -> V2ModelReadResponse:
        """
        Get a model object.

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
                "/v2/{entity}/{project}/models/{object_id}/versions/{digest}",
                entity=entity,
                project=project,
                object_id=object_id,
                digest=digest,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2ModelReadResponse,
        )


class AsyncV2ModelsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncV2ModelsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncV2ModelsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncV2ModelsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncV2ModelsResourceWithStreamingResponse(self)

    async def create(
        self,
        project: str,
        *,
        entity: str,
        name: str,
        source_code: str,
        attributes: Optional[Dict[str, object]] | Omit = omit,
        description: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2ModelCreateResponse:
        """Create a model object.

        Args:
          name: The name of this model.

        Models with the same name will be versioned together.

          source_code: Complete source code for the Model class including imports

          attributes: Additional attributes to be stored with the model

          description: A description of this model

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
            path_template("/v2/{entity}/{project}/models", entity=entity, project=project),
            body=await async_maybe_transform(
                {
                    "name": name,
                    "source_code": source_code,
                    "attributes": attributes,
                    "description": description,
                },
                v2_model_create_params.V2ModelCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2ModelCreateResponse,
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
        List model objects.

        Args:
          limit: Maximum number of models to return

          offset: Number of models to skip

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
            path_template("/v2/{entity}/{project}/models", entity=entity, project=project),
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
                    v2_model_list_params.V2ModelListParams,
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
    ) -> V2ModelDeleteResponse:
        """Delete a model object.

        If digests are provided, only those versions are deleted.
        Otherwise, all versions are deleted.

        Args:
          digests: List of digests to delete. If not provided, all digests for the model will be
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
                "/v2/{entity}/{project}/models/{object_id}", entity=entity, project=project, object_id=object_id
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"digests": digests}, v2_model_delete_params.V2ModelDeleteParams),
            ),
            cast_to=V2ModelDeleteResponse,
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
    ) -> V2ModelReadResponse:
        """
        Get a model object.

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
                "/v2/{entity}/{project}/models/{object_id}/versions/{digest}",
                entity=entity,
                project=project,
                object_id=object_id,
                digest=digest,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2ModelReadResponse,
        )


class V2ModelsResourceWithRawResponse:
    def __init__(self, v2_models: V2ModelsResource) -> None:
        self._v2_models = v2_models

        self.create = to_raw_response_wrapper(
            v2_models.create,
        )
        self.list = to_raw_response_wrapper(
            v2_models.list,
        )
        self.delete = to_raw_response_wrapper(
            v2_models.delete,
        )
        self.read = to_raw_response_wrapper(
            v2_models.read,
        )


class AsyncV2ModelsResourceWithRawResponse:
    def __init__(self, v2_models: AsyncV2ModelsResource) -> None:
        self._v2_models = v2_models

        self.create = async_to_raw_response_wrapper(
            v2_models.create,
        )
        self.list = async_to_raw_response_wrapper(
            v2_models.list,
        )
        self.delete = async_to_raw_response_wrapper(
            v2_models.delete,
        )
        self.read = async_to_raw_response_wrapper(
            v2_models.read,
        )


class V2ModelsResourceWithStreamingResponse:
    def __init__(self, v2_models: V2ModelsResource) -> None:
        self._v2_models = v2_models

        self.create = to_streamed_response_wrapper(
            v2_models.create,
        )
        self.list = to_streamed_response_wrapper(
            v2_models.list,
        )
        self.delete = to_streamed_response_wrapper(
            v2_models.delete,
        )
        self.read = to_streamed_response_wrapper(
            v2_models.read,
        )


class AsyncV2ModelsResourceWithStreamingResponse:
    def __init__(self, v2_models: AsyncV2ModelsResource) -> None:
        self._v2_models = v2_models

        self.create = async_to_streamed_response_wrapper(
            v2_models.create,
        )
        self.list = async_to_streamed_response_wrapper(
            v2_models.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            v2_models.delete,
        )
        self.read = async_to_streamed_response_wrapper(
            v2_models.read,
        )
