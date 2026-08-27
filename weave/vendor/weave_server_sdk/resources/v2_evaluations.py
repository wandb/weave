# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional

import httpx

from ..types import v2_evaluation_list_params, v2_evaluation_create_params, v2_evaluation_delete_params
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
from .._decoders.jsonl import JSONLDecoder, AsyncJSONLDecoder
from ..types.v2_evaluation_list_response import V2EvaluationListResponse
from ..types.v2_evaluation_read_response import V2EvaluationReadResponse
from ..types.v2_evaluation_create_response import V2EvaluationCreateResponse
from ..types.v2_evaluation_delete_response import V2EvaluationDeleteResponse

__all__ = ["V2EvaluationsResource", "AsyncV2EvaluationsResource"]


class V2EvaluationsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> V2EvaluationsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return V2EvaluationsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> V2EvaluationsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return V2EvaluationsResourceWithStreamingResponse(self)

    def create(
        self,
        project: str,
        *,
        entity: str,
        dataset: str,
        name: str,
        description: Optional[str] | Omit = omit,
        eval_attributes: Optional[Dict[str, object]] | Omit = omit,
        evaluation_name: Optional[str] | Omit = omit,
        scorers: Optional[SequenceNotStr[str]] | Omit = omit,
        trials: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvaluationCreateResponse:
        """
        Create an evaluation object.

        Args:
          dataset: Reference to the dataset (weave:// URI)

          name: The name of this evaluation. Evaluations with the same name will be versioned
              together.

          description: A description of this evaluation

          eval_attributes: Optional attributes for the evaluation

          evaluation_name: Name for the evaluation run

          scorers: List of scorer references (weave:// URIs)

          trials: Number of trials to run

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
            path_template("/v2/{entity}/{project}/evaluations", entity=entity, project=project),
            body=maybe_transform(
                {
                    "dataset": dataset,
                    "name": name,
                    "description": description,
                    "eval_attributes": eval_attributes,
                    "evaluation_name": evaluation_name,
                    "scorers": scorers,
                    "trials": trials,
                },
                v2_evaluation_create_params.V2EvaluationCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvaluationCreateResponse,
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
    ) -> JSONLDecoder[V2EvaluationListResponse]:
        """
        List evaluation objects.

        Args:
          limit: Maximum number of evaluations to return

          offset: Number of evaluations to skip

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        extra_headers = {"Accept": "application/x-ndjson", **(extra_headers or {})}
        return self._get(
            path_template("/v2/{entity}/{project}/evaluations", entity=entity, project=project),
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
                    v2_evaluation_list_params.V2EvaluationListParams,
                ),
            ),
            cast_to=JSONLDecoder[V2EvaluationListResponse],
            stream=True,
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
    ) -> V2EvaluationDeleteResponse:
        """Delete an evaluation object.

        Args:
          digests: List of digests to delete.

        If not provided, all digests for the evaluation will
              be deleted.

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
                "/v2/{entity}/{project}/evaluations/{object_id}", entity=entity, project=project, object_id=object_id
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform({"digests": digests}, v2_evaluation_delete_params.V2EvaluationDeleteParams),
            ),
            cast_to=V2EvaluationDeleteResponse,
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
    ) -> V2EvaluationReadResponse:
        """
        Get an evaluation object.

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
                "/v2/{entity}/{project}/evaluations/{object_id}/versions/{digest}",
                entity=entity,
                project=project,
                object_id=object_id,
                digest=digest,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvaluationReadResponse,
        )


class AsyncV2EvaluationsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncV2EvaluationsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncV2EvaluationsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncV2EvaluationsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncV2EvaluationsResourceWithStreamingResponse(self)

    async def create(
        self,
        project: str,
        *,
        entity: str,
        dataset: str,
        name: str,
        description: Optional[str] | Omit = omit,
        eval_attributes: Optional[Dict[str, object]] | Omit = omit,
        evaluation_name: Optional[str] | Omit = omit,
        scorers: Optional[SequenceNotStr[str]] | Omit = omit,
        trials: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvaluationCreateResponse:
        """
        Create an evaluation object.

        Args:
          dataset: Reference to the dataset (weave:// URI)

          name: The name of this evaluation. Evaluations with the same name will be versioned
              together.

          description: A description of this evaluation

          eval_attributes: Optional attributes for the evaluation

          evaluation_name: Name for the evaluation run

          scorers: List of scorer references (weave:// URIs)

          trials: Number of trials to run

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
            path_template("/v2/{entity}/{project}/evaluations", entity=entity, project=project),
            body=await async_maybe_transform(
                {
                    "dataset": dataset,
                    "name": name,
                    "description": description,
                    "eval_attributes": eval_attributes,
                    "evaluation_name": evaluation_name,
                    "scorers": scorers,
                    "trials": trials,
                },
                v2_evaluation_create_params.V2EvaluationCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvaluationCreateResponse,
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
    ) -> AsyncJSONLDecoder[V2EvaluationListResponse]:
        """
        List evaluation objects.

        Args:
          limit: Maximum number of evaluations to return

          offset: Number of evaluations to skip

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        extra_headers = {"Accept": "application/x-ndjson", **(extra_headers or {})}
        return await self._get(
            path_template("/v2/{entity}/{project}/evaluations", entity=entity, project=project),
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
                    v2_evaluation_list_params.V2EvaluationListParams,
                ),
            ),
            cast_to=AsyncJSONLDecoder[V2EvaluationListResponse],
            stream=True,
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
    ) -> V2EvaluationDeleteResponse:
        """Delete an evaluation object.

        Args:
          digests: List of digests to delete.

        If not provided, all digests for the evaluation will
              be deleted.

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
                "/v2/{entity}/{project}/evaluations/{object_id}", entity=entity, project=project, object_id=object_id
            ),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"digests": digests}, v2_evaluation_delete_params.V2EvaluationDeleteParams
                ),
            ),
            cast_to=V2EvaluationDeleteResponse,
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
    ) -> V2EvaluationReadResponse:
        """
        Get an evaluation object.

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
                "/v2/{entity}/{project}/evaluations/{object_id}/versions/{digest}",
                entity=entity,
                project=project,
                object_id=object_id,
                digest=digest,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvaluationReadResponse,
        )


class V2EvaluationsResourceWithRawResponse:
    def __init__(self, v2_evaluations: V2EvaluationsResource) -> None:
        self._v2_evaluations = v2_evaluations

        self.create = to_raw_response_wrapper(
            v2_evaluations.create,
        )
        self.list = to_raw_response_wrapper(
            v2_evaluations.list,
        )
        self.delete = to_raw_response_wrapper(
            v2_evaluations.delete,
        )
        self.read = to_raw_response_wrapper(
            v2_evaluations.read,
        )


class AsyncV2EvaluationsResourceWithRawResponse:
    def __init__(self, v2_evaluations: AsyncV2EvaluationsResource) -> None:
        self._v2_evaluations = v2_evaluations

        self.create = async_to_raw_response_wrapper(
            v2_evaluations.create,
        )
        self.list = async_to_raw_response_wrapper(
            v2_evaluations.list,
        )
        self.delete = async_to_raw_response_wrapper(
            v2_evaluations.delete,
        )
        self.read = async_to_raw_response_wrapper(
            v2_evaluations.read,
        )


class V2EvaluationsResourceWithStreamingResponse:
    def __init__(self, v2_evaluations: V2EvaluationsResource) -> None:
        self._v2_evaluations = v2_evaluations

        self.create = to_streamed_response_wrapper(
            v2_evaluations.create,
        )
        self.list = to_streamed_response_wrapper(
            v2_evaluations.list,
        )
        self.delete = to_streamed_response_wrapper(
            v2_evaluations.delete,
        )
        self.read = to_streamed_response_wrapper(
            v2_evaluations.read,
        )


class AsyncV2EvaluationsResourceWithStreamingResponse:
    def __init__(self, v2_evaluations: AsyncV2EvaluationsResource) -> None:
        self._v2_evaluations = v2_evaluations

        self.create = async_to_streamed_response_wrapper(
            v2_evaluations.create,
        )
        self.list = async_to_streamed_response_wrapper(
            v2_evaluations.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            v2_evaluations.delete,
        )
        self.read = async_to_streamed_response_wrapper(
            v2_evaluations.read,
        )
