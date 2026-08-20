# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Optional

import httpx

from ..types import (
    v2_evaluation_run_list_params,
    v2_evaluation_run_create_params,
    v2_evaluation_run_delete_params,
    v2_evaluation_run_finish_params,
)
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
from ..types.v2_evaluation_run_list_response import V2EvaluationRunListResponse
from ..types.v2_evaluation_run_read_response import V2EvaluationRunReadResponse
from ..types.v2_evaluation_run_create_response import V2EvaluationRunCreateResponse
from ..types.v2_evaluation_run_delete_response import V2EvaluationRunDeleteResponse
from ..types.v2_evaluation_run_finish_response import V2EvaluationRunFinishResponse

__all__ = ["V2EvaluationRunsResource", "AsyncV2EvaluationRunsResource"]


class V2EvaluationRunsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> V2EvaluationRunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return V2EvaluationRunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> V2EvaluationRunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return V2EvaluationRunsResourceWithStreamingResponse(self)

    def create(
        self,
        project: str,
        *,
        entity: str,
        evaluation: str,
        model: str,
        source_evaluation_run_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvaluationRunCreateResponse:
        """
        Create an evaluation run.

        Args:
          evaluation: Reference to the evaluation (weave:// URI)

          model: Reference to the model (weave:// URI)

          source_evaluation_run_id: Source evaluation run ID if this run was created by rescoring — provenance link

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
            path_template("/v2/{entity}/{project}/evaluation_runs", entity=entity, project=project),
            body=maybe_transform(
                {
                    "evaluation": evaluation,
                    "model": model,
                    "source_evaluation_run_id": source_evaluation_run_id,
                },
                v2_evaluation_run_create_params.V2EvaluationRunCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvaluationRunCreateResponse,
        )

    def list(
        self,
        project: str,
        *,
        entity: str,
        evaluation_run_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        evaluations: Optional[SequenceNotStr[str]] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        models: Optional[SequenceNotStr[str]] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> JSONLDecoder[V2EvaluationRunListResponse]:
        """
        List evaluation runs.

        Args:
          evaluation_run_ids: Filter by evaluation run IDs

          evaluations: Filter by evaluation references

          limit: Maximum number of evaluation runs to return

          models: Filter by model references

          offset: Number of evaluation runs to skip

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        extra_headers = {"Accept": "application/jsonl", **(extra_headers or {})}
        return self._get(
            path_template("/v2/{entity}/{project}/evaluation_runs", entity=entity, project=project),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {
                        "evaluation_run_ids": evaluation_run_ids,
                        "evaluations": evaluations,
                        "limit": limit,
                        "models": models,
                        "offset": offset,
                    },
                    v2_evaluation_run_list_params.V2EvaluationRunListParams,
                ),
            ),
            cast_to=JSONLDecoder[V2EvaluationRunListResponse],
            stream=True,
        )

    def delete(
        self,
        project: str,
        *,
        entity: str,
        evaluation_run_ids: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvaluationRunDeleteResponse:
        """
        Delete evaluation runs.

        Args:
          evaluation_run_ids: List of evaluation run IDs to delete

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        return self._delete(
            path_template("/v2/{entity}/{project}/evaluation_runs", entity=entity, project=project),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"evaluation_run_ids": evaluation_run_ids},
                    v2_evaluation_run_delete_params.V2EvaluationRunDeleteParams,
                ),
            ),
            cast_to=V2EvaluationRunDeleteResponse,
        )

    def finish(
        self,
        evaluation_run_id: str,
        *,
        entity: str,
        project: str,
        summary: Optional[Dict[str, object]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvaluationRunFinishResponse:
        """
        Finish an evaluation run.

        Args:
          summary: Optional summary dictionary for the evaluation run

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        if not evaluation_run_id:
            raise ValueError(f"Expected a non-empty value for `evaluation_run_id` but received {evaluation_run_id!r}")
        return self._post(
            path_template(
                "/v2/{entity}/{project}/evaluation_runs/{evaluation_run_id}/finish",
                entity=entity,
                project=project,
                evaluation_run_id=evaluation_run_id,
            ),
            body=maybe_transform({"summary": summary}, v2_evaluation_run_finish_params.V2EvaluationRunFinishParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvaluationRunFinishResponse,
        )

    def read(
        self,
        evaluation_run_id: str,
        *,
        entity: str,
        project: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvaluationRunReadResponse:
        """
        Read an evaluation run.

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
        if not evaluation_run_id:
            raise ValueError(f"Expected a non-empty value for `evaluation_run_id` but received {evaluation_run_id!r}")
        return self._get(
            path_template(
                "/v2/{entity}/{project}/evaluation_runs/{evaluation_run_id}",
                entity=entity,
                project=project,
                evaluation_run_id=evaluation_run_id,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvaluationRunReadResponse,
        )


class AsyncV2EvaluationRunsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncV2EvaluationRunsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncV2EvaluationRunsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncV2EvaluationRunsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncV2EvaluationRunsResourceWithStreamingResponse(self)

    async def create(
        self,
        project: str,
        *,
        entity: str,
        evaluation: str,
        model: str,
        source_evaluation_run_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvaluationRunCreateResponse:
        """
        Create an evaluation run.

        Args:
          evaluation: Reference to the evaluation (weave:// URI)

          model: Reference to the model (weave:// URI)

          source_evaluation_run_id: Source evaluation run ID if this run was created by rescoring — provenance link

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
            path_template("/v2/{entity}/{project}/evaluation_runs", entity=entity, project=project),
            body=await async_maybe_transform(
                {
                    "evaluation": evaluation,
                    "model": model,
                    "source_evaluation_run_id": source_evaluation_run_id,
                },
                v2_evaluation_run_create_params.V2EvaluationRunCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvaluationRunCreateResponse,
        )

    async def list(
        self,
        project: str,
        *,
        entity: str,
        evaluation_run_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        evaluations: Optional[SequenceNotStr[str]] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        models: Optional[SequenceNotStr[str]] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AsyncJSONLDecoder[V2EvaluationRunListResponse]:
        """
        List evaluation runs.

        Args:
          evaluation_run_ids: Filter by evaluation run IDs

          evaluations: Filter by evaluation references

          limit: Maximum number of evaluation runs to return

          models: Filter by model references

          offset: Number of evaluation runs to skip

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        extra_headers = {"Accept": "application/jsonl", **(extra_headers or {})}
        return await self._get(
            path_template("/v2/{entity}/{project}/evaluation_runs", entity=entity, project=project),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {
                        "evaluation_run_ids": evaluation_run_ids,
                        "evaluations": evaluations,
                        "limit": limit,
                        "models": models,
                        "offset": offset,
                    },
                    v2_evaluation_run_list_params.V2EvaluationRunListParams,
                ),
            ),
            cast_to=AsyncJSONLDecoder[V2EvaluationRunListResponse],
            stream=True,
        )

    async def delete(
        self,
        project: str,
        *,
        entity: str,
        evaluation_run_ids: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvaluationRunDeleteResponse:
        """
        Delete evaluation runs.

        Args:
          evaluation_run_ids: List of evaluation run IDs to delete

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        return await self._delete(
            path_template("/v2/{entity}/{project}/evaluation_runs", entity=entity, project=project),
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"evaluation_run_ids": evaluation_run_ids},
                    v2_evaluation_run_delete_params.V2EvaluationRunDeleteParams,
                ),
            ),
            cast_to=V2EvaluationRunDeleteResponse,
        )

    async def finish(
        self,
        evaluation_run_id: str,
        *,
        entity: str,
        project: str,
        summary: Optional[Dict[str, object]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvaluationRunFinishResponse:
        """
        Finish an evaluation run.

        Args:
          summary: Optional summary dictionary for the evaluation run

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        if not entity:
            raise ValueError(f"Expected a non-empty value for `entity` but received {entity!r}")
        if not project:
            raise ValueError(f"Expected a non-empty value for `project` but received {project!r}")
        if not evaluation_run_id:
            raise ValueError(f"Expected a non-empty value for `evaluation_run_id` but received {evaluation_run_id!r}")
        return await self._post(
            path_template(
                "/v2/{entity}/{project}/evaluation_runs/{evaluation_run_id}/finish",
                entity=entity,
                project=project,
                evaluation_run_id=evaluation_run_id,
            ),
            body=await async_maybe_transform(
                {"summary": summary}, v2_evaluation_run_finish_params.V2EvaluationRunFinishParams
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvaluationRunFinishResponse,
        )

    async def read(
        self,
        evaluation_run_id: str,
        *,
        entity: str,
        project: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvaluationRunReadResponse:
        """
        Read an evaluation run.

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
        if not evaluation_run_id:
            raise ValueError(f"Expected a non-empty value for `evaluation_run_id` but received {evaluation_run_id!r}")
        return await self._get(
            path_template(
                "/v2/{entity}/{project}/evaluation_runs/{evaluation_run_id}",
                entity=entity,
                project=project,
                evaluation_run_id=evaluation_run_id,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvaluationRunReadResponse,
        )


class V2EvaluationRunsResourceWithRawResponse:
    def __init__(self, v2_evaluation_runs: V2EvaluationRunsResource) -> None:
        self._v2_evaluation_runs = v2_evaluation_runs

        self.create = to_raw_response_wrapper(
            v2_evaluation_runs.create,
        )
        self.list = to_raw_response_wrapper(
            v2_evaluation_runs.list,
        )
        self.delete = to_raw_response_wrapper(
            v2_evaluation_runs.delete,
        )
        self.finish = to_raw_response_wrapper(
            v2_evaluation_runs.finish,
        )
        self.read = to_raw_response_wrapper(
            v2_evaluation_runs.read,
        )


class AsyncV2EvaluationRunsResourceWithRawResponse:
    def __init__(self, v2_evaluation_runs: AsyncV2EvaluationRunsResource) -> None:
        self._v2_evaluation_runs = v2_evaluation_runs

        self.create = async_to_raw_response_wrapper(
            v2_evaluation_runs.create,
        )
        self.list = async_to_raw_response_wrapper(
            v2_evaluation_runs.list,
        )
        self.delete = async_to_raw_response_wrapper(
            v2_evaluation_runs.delete,
        )
        self.finish = async_to_raw_response_wrapper(
            v2_evaluation_runs.finish,
        )
        self.read = async_to_raw_response_wrapper(
            v2_evaluation_runs.read,
        )


class V2EvaluationRunsResourceWithStreamingResponse:
    def __init__(self, v2_evaluation_runs: V2EvaluationRunsResource) -> None:
        self._v2_evaluation_runs = v2_evaluation_runs

        self.create = to_streamed_response_wrapper(
            v2_evaluation_runs.create,
        )
        self.list = to_streamed_response_wrapper(
            v2_evaluation_runs.list,
        )
        self.delete = to_streamed_response_wrapper(
            v2_evaluation_runs.delete,
        )
        self.finish = to_streamed_response_wrapper(
            v2_evaluation_runs.finish,
        )
        self.read = to_streamed_response_wrapper(
            v2_evaluation_runs.read,
        )


class AsyncV2EvaluationRunsResourceWithStreamingResponse:
    def __init__(self, v2_evaluation_runs: AsyncV2EvaluationRunsResource) -> None:
        self._v2_evaluation_runs = v2_evaluation_runs

        self.create = async_to_streamed_response_wrapper(
            v2_evaluation_runs.create,
        )
        self.list = async_to_streamed_response_wrapper(
            v2_evaluation_runs.list,
        )
        self.delete = async_to_streamed_response_wrapper(
            v2_evaluation_runs.delete,
        )
        self.finish = async_to_streamed_response_wrapper(
            v2_evaluation_runs.finish,
        )
        self.read = async_to_streamed_response_wrapper(
            v2_evaluation_runs.read,
        )
