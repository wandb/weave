# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional

import httpx

from ..types import v2_op_list_params, v2_op_read_params, v2_op_create_params, v2_op_delete_params
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
from ..types.v2_op_read_response import V2OpReadResponse
from ..types.v2_op_create_response import V2OpCreateResponse
from ..types.v2_op_delete_response import V2OpDeleteResponse

__all__ = ["V2OpsResource", "AsyncV2OpsResource"]


class V2OpsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> V2OpsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return V2OpsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> V2OpsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return V2OpsResourceWithStreamingResponse(self)

    def create(
        self,
        project: str,
        *,
        entity: str,
        name: Optional[str] | Omit = omit,
        source_code: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2OpCreateResponse:
        """Create an op object.

        Args:
          name: The name of this op.

        Ops with the same name will be versioned together.

          source_code: Complete source code for this op, including imports

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
            path_template("/v2/{entity}/{project}/ops", entity=entity, project=project),
            body=maybe_transform(
                {
                    "name": name,
                    "source_code": source_code,
                },
                v2_op_create_params.V2OpCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2OpCreateResponse,
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
        List op objects.

        Args:
          limit: Maximum number of ops to return

          offset: Number of ops to skip

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
            path_template("/v2/{entity}/{project}/ops", entity=entity, project=project),
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
                    v2_op_list_params.V2OpListParams,
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
    ) -> V2OpDeleteResponse:
        """Delete an op object.

        If digests are provided, only those versions are deleted.
        Otherwise, all versions are deleted.

        Args:
          digests: List of digests to delete. If not provided, all digests for the op will be
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
                "/v2/{entity}/{project}/ops/{object_id}", entity=entity, project=project, object_id=object_id
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"digests": digests}, v2_op_delete_params.V2OpDeleteParams),
            ),
            cast_to=V2OpDeleteResponse,
        )

    def read(
        self,
        digest: str,
        *,
        entity: str,
        project: str,
        object_id: str,
        eager: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2OpReadResponse:
        """
        Get an op object.

        Args:
          eager: Whether to eagerly load the op code

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
                "/v2/{entity}/{project}/ops/{object_id}/versions/{digest}",
                entity=entity,
                project=project,
                object_id=object_id,
                digest=digest,
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"eager": eager}, v2_op_read_params.V2OpReadParams),
            ),
            cast_to=V2OpReadResponse,
        )


class AsyncV2OpsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncV2OpsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncV2OpsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncV2OpsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncV2OpsResourceWithStreamingResponse(self)

    async def create(
        self,
        project: str,
        *,
        entity: str,
        name: Optional[str] | Omit = omit,
        source_code: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2OpCreateResponse:
        """Create an op object.

        Args:
          name: The name of this op.

        Ops with the same name will be versioned together.

          source_code: Complete source code for this op, including imports

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
            path_template("/v2/{entity}/{project}/ops", entity=entity, project=project),
            body=await async_maybe_transform(
                {
                    "name": name,
                    "source_code": source_code,
                },
                v2_op_create_params.V2OpCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2OpCreateResponse,
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
        List op objects.

        Args:
          limit: Maximum number of ops to return

          offset: Number of ops to skip

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
            path_template("/v2/{entity}/{project}/ops", entity=entity, project=project),
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
                    v2_op_list_params.V2OpListParams,
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
    ) -> V2OpDeleteResponse:
        """Delete an op object.

        If digests are provided, only those versions are deleted.
        Otherwise, all versions are deleted.

        Args:
          digests: List of digests to delete. If not provided, all digests for the op will be
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
                "/v2/{entity}/{project}/ops/{object_id}", entity=entity, project=project, object_id=object_id
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"digests": digests}, v2_op_delete_params.V2OpDeleteParams),
            ),
            cast_to=V2OpDeleteResponse,
        )

    async def read(
        self,
        digest: str,
        *,
        entity: str,
        project: str,
        object_id: str,
        eager: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2OpReadResponse:
        """
        Get an op object.

        Args:
          eager: Whether to eagerly load the op code

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
                "/v2/{entity}/{project}/ops/{object_id}/versions/{digest}",
                entity=entity,
                project=project,
                object_id=object_id,
                digest=digest,
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"eager": eager}, v2_op_read_params.V2OpReadParams),
            ),
            cast_to=V2OpReadResponse,
        )


class V2OpsResourceWithRawResponse:
    def __init__(self, v2_ops: V2OpsResource) -> None:
        self._v2_ops = v2_ops

        self.create = to_raw_response_wrapper(
            v2_ops.create,
        )
        self.list = to_raw_response_wrapper(
            v2_ops.list,
        )
        self.delete = to_raw_response_wrapper(
            v2_ops.delete,
        )
        self.read = to_raw_response_wrapper(
            v2_ops.read,
        )


class AsyncV2OpsResourceWithRawResponse:
    def __init__(self, v2_ops: AsyncV2OpsResource) -> None:
        self._v2_ops = v2_ops

        self.create = async_to_raw_response_wrapper(
            v2_ops.create,
        )
        self.list = async_to_raw_response_wrapper(
            v2_ops.list,
        )
        self.delete = async_to_raw_response_wrapper(
            v2_ops.delete,
        )
        self.read = async_to_raw_response_wrapper(
            v2_ops.read,
        )


class V2OpsResourceWithStreamingResponse:
    def __init__(self, v2_ops: V2OpsResource) -> None:
        self._v2_ops = v2_ops

        self.create = to_streamed_response_wrapper(
            v2_ops.create,
        )
        self.list = to_streamed_response_wrapper(
            v2_ops.list,
        )
        self.delete = to_streamed_response_wrapper(
            v2_ops.delete,
        )
        self.read = to_streamed_response_wrapper(
            v2_ops.read,
        )


class AsyncV2OpsResourceWithStreamingResponse:
    def __init__(self, v2_ops: AsyncV2OpsResource) -> None:
        self._v2_ops = v2_ops

        self.create = async_to_streamed_response_wrapper(
            v2_ops.create,
        )
        self.list = async_to_streamed_response_wrapper(
            v2_ops.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            v2_ops.delete,
        )
        self.read = async_to_streamed_response_wrapper(
            v2_ops.read,
        )
