# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional

import httpx

from ..types import v2_scorer_create_params, v2_scorer_delete_params
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
from ..types.v2_scorer_read_response import V2ScorerReadResponse
from ..types.v2_scorer_create_response import V2ScorerCreateResponse
from ..types.v2_scorer_delete_response import V2ScorerDeleteResponse

__all__ = ["V2ScorersResource", "AsyncV2ScorersResource"]


class V2ScorersResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> V2ScorersResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return V2ScorersResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> V2ScorersResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return V2ScorersResourceWithStreamingResponse(self)

    def create(
        self,
        project: str,
        *,
        entity: str,
        name: str,
        op_source_code: str,
        description: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2ScorerCreateResponse:
        """Create a scorer object.

        Args:
          name: The name of this scorer.

        Scorers with the same name will be versioned together.

          op_source_code: Complete source code for the Scorer.score op including imports

          description: A description of this scorer

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
            path_template("/v2/{entity}/{project}/scorers", entity=entity, project=project),
            body=maybe_transform(
                {
                    "name": name,
                    "op_source_code": op_source_code,
                    "description": description,
                },
                v2_scorer_create_params.V2ScorerCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2ScorerCreateResponse,
        )

    def list(
        self,
        project: str,
        *,
        entity: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        List scorer objects.

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
        return self._get(
            path_template("/v2/{entity}/{project}/scorers", entity=entity, project=project),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
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
    ) -> V2ScorerDeleteResponse:
        """Delete a scorer object.

        Args:
          digests: List of digests to delete.

        If not provided, all digests for the scorer will be
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
                "/v2/{entity}/{project}/scorers/{object_id}", entity=entity, project=project, object_id=object_id
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"digests": digests}, v2_scorer_delete_params.V2ScorerDeleteParams),
            ),
            cast_to=V2ScorerDeleteResponse,
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
    ) -> V2ScorerReadResponse:
        """
        Get a scorer object.

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
                "/v2/{entity}/{project}/scorers/{object_id}/versions/{digest}",
                entity=entity,
                project=project,
                object_id=object_id,
                digest=digest,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2ScorerReadResponse,
        )


class AsyncV2ScorersResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncV2ScorersResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncV2ScorersResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncV2ScorersResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncV2ScorersResourceWithStreamingResponse(self)

    async def create(
        self,
        project: str,
        *,
        entity: str,
        name: str,
        op_source_code: str,
        description: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2ScorerCreateResponse:
        """Create a scorer object.

        Args:
          name: The name of this scorer.

        Scorers with the same name will be versioned together.

          op_source_code: Complete source code for the Scorer.score op including imports

          description: A description of this scorer

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
            path_template("/v2/{entity}/{project}/scorers", entity=entity, project=project),
            body=await async_maybe_transform(
                {
                    "name": name,
                    "op_source_code": op_source_code,
                    "description": description,
                },
                v2_scorer_create_params.V2ScorerCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2ScorerCreateResponse,
        )

    async def list(
        self,
        project: str,
        *,
        entity: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        List scorer objects.

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
        return await self._get(
            path_template("/v2/{entity}/{project}/scorers", entity=entity, project=project),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
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
    ) -> V2ScorerDeleteResponse:
        """Delete a scorer object.

        Args:
          digests: List of digests to delete.

        If not provided, all digests for the scorer will be
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
                "/v2/{entity}/{project}/scorers/{object_id}", entity=entity, project=project, object_id=object_id
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform({"digests": digests}, v2_scorer_delete_params.V2ScorerDeleteParams),
            ),
            cast_to=V2ScorerDeleteResponse,
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
    ) -> V2ScorerReadResponse:
        """
        Get a scorer object.

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
                "/v2/{entity}/{project}/scorers/{object_id}/versions/{digest}",
                entity=entity,
                project=project,
                object_id=object_id,
                digest=digest,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2ScorerReadResponse,
        )


class V2ScorersResourceWithRawResponse:
    def __init__(self, v2_scorers: V2ScorersResource) -> None:
        self._v2_scorers = v2_scorers

        self.create = to_raw_response_wrapper(
            v2_scorers.create,
        )
        self.list = to_raw_response_wrapper(
            v2_scorers.list,
        )
        self.delete = to_raw_response_wrapper(
            v2_scorers.delete,
        )
        self.read = to_raw_response_wrapper(
            v2_scorers.read,
        )


class AsyncV2ScorersResourceWithRawResponse:
    def __init__(self, v2_scorers: AsyncV2ScorersResource) -> None:
        self._v2_scorers = v2_scorers

        self.create = async_to_raw_response_wrapper(
            v2_scorers.create,
        )
        self.list = async_to_raw_response_wrapper(
            v2_scorers.list,
        )
        self.delete = async_to_raw_response_wrapper(
            v2_scorers.delete,
        )
        self.read = async_to_raw_response_wrapper(
            v2_scorers.read,
        )


class V2ScorersResourceWithStreamingResponse:
    def __init__(self, v2_scorers: V2ScorersResource) -> None:
        self._v2_scorers = v2_scorers

        self.create = to_streamed_response_wrapper(
            v2_scorers.create,
        )
        self.list = to_streamed_response_wrapper(
            v2_scorers.list,
        )
        self.delete = to_streamed_response_wrapper(
            v2_scorers.delete,
        )
        self.read = to_streamed_response_wrapper(
            v2_scorers.read,
        )


class AsyncV2ScorersResourceWithStreamingResponse:
    def __init__(self, v2_scorers: AsyncV2ScorersResource) -> None:
        self._v2_scorers = v2_scorers

        self.create = async_to_streamed_response_wrapper(
            v2_scorers.create,
        )
        self.list = async_to_streamed_response_wrapper(
            v2_scorers.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            v2_scorers.delete,
        )
        self.read = async_to_streamed_response_wrapper(
            v2_scorers.read,
        )
