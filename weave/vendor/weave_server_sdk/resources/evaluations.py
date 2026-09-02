# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional

import httpx

from ..types import evaluation_status_params, evaluation_rescore_params, evaluation_evaluate_model_params
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
from ..types.evaluation_status_response import EvaluationStatusResponse
from ..types.evaluation_rescore_response import EvaluationRescoreResponse
from ..types.evaluation_evaluate_model_response import EvaluationEvaluateModelResponse

__all__ = ["EvaluationsResource", "AsyncEvaluationsResource"]


class EvaluationsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> EvaluationsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return EvaluationsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> EvaluationsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return EvaluationsResourceWithStreamingResponse(self)

    def evaluate_model(
        self,
        *,
        evaluation_ref: str,
        model_ref: str,
        project_id: str,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> EvaluationEvaluateModelResponse:
        """Evaluate Model

        Args:
          wb_user_id: Do not set directly.

        Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/evaluations/evaluate_model",
            body=maybe_transform(
                {
                    "evaluation_ref": evaluation_ref,
                    "model_ref": model_ref,
                    "project_id": project_id,
                    "wb_user_id": wb_user_id,
                },
                evaluation_evaluate_model_params.EvaluationEvaluateModelParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=EvaluationEvaluateModelResponse,
        )

    def rescore(
        self,
        *,
        project_id: str,
        scorer_refs: SequenceNotStr[str],
        source_evaluation_run_id: str,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> EvaluationRescoreResponse:
        """
        Rescore an existing evaluation run with different scorer(s).

        Applies the provided scorer(s) to the predictions from source_evaluation_run_id
        and returns a new evaluation_run_id. Original prediction call IDs are preserved.

        Args:
          scorer_refs: Scorer references (weave:// URIs) to apply; must be non-empty

          source_evaluation_run_id: The evaluation run whose predictions will be rescored

          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/evaluations/rescore",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "scorer_refs": scorer_refs,
                    "source_evaluation_run_id": source_evaluation_run_id,
                    "wb_user_id": wb_user_id,
                },
                evaluation_rescore_params.EvaluationRescoreParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=EvaluationRescoreResponse,
        )

    def status(
        self,
        *,
        call_id: str,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> EvaluationStatusResponse:
        """
        Evaluation Status

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/evaluations/status",
            body=maybe_transform(
                {
                    "call_id": call_id,
                    "project_id": project_id,
                },
                evaluation_status_params.EvaluationStatusParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=EvaluationStatusResponse,
        )


class AsyncEvaluationsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncEvaluationsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncEvaluationsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncEvaluationsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncEvaluationsResourceWithStreamingResponse(self)

    async def evaluate_model(
        self,
        *,
        evaluation_ref: str,
        model_ref: str,
        project_id: str,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> EvaluationEvaluateModelResponse:
        """Evaluate Model

        Args:
          wb_user_id: Do not set directly.

        Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/evaluations/evaluate_model",
            body=await async_maybe_transform(
                {
                    "evaluation_ref": evaluation_ref,
                    "model_ref": model_ref,
                    "project_id": project_id,
                    "wb_user_id": wb_user_id,
                },
                evaluation_evaluate_model_params.EvaluationEvaluateModelParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=EvaluationEvaluateModelResponse,
        )

    async def rescore(
        self,
        *,
        project_id: str,
        scorer_refs: SequenceNotStr[str],
        source_evaluation_run_id: str,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> EvaluationRescoreResponse:
        """
        Rescore an existing evaluation run with different scorer(s).

        Applies the provided scorer(s) to the predictions from source_evaluation_run_id
        and returns a new evaluation_run_id. Original prediction call IDs are preserved.

        Args:
          scorer_refs: Scorer references (weave:// URIs) to apply; must be non-empty

          source_evaluation_run_id: The evaluation run whose predictions will be rescored

          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/evaluations/rescore",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "scorer_refs": scorer_refs,
                    "source_evaluation_run_id": source_evaluation_run_id,
                    "wb_user_id": wb_user_id,
                },
                evaluation_rescore_params.EvaluationRescoreParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=EvaluationRescoreResponse,
        )

    async def status(
        self,
        *,
        call_id: str,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> EvaluationStatusResponse:
        """
        Evaluation Status

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/evaluations/status",
            body=await async_maybe_transform(
                {
                    "call_id": call_id,
                    "project_id": project_id,
                },
                evaluation_status_params.EvaluationStatusParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=EvaluationStatusResponse,
        )


class EvaluationsResourceWithRawResponse:
    def __init__(self, evaluations: EvaluationsResource) -> None:
        self._evaluations = evaluations

        self.evaluate_model = to_raw_response_wrapper(
            evaluations.evaluate_model,
        )
        self.rescore = to_raw_response_wrapper(
            evaluations.rescore,
        )
        self.status = to_raw_response_wrapper(
            evaluations.status,
        )


class AsyncEvaluationsResourceWithRawResponse:
    def __init__(self, evaluations: AsyncEvaluationsResource) -> None:
        self._evaluations = evaluations

        self.evaluate_model = async_to_raw_response_wrapper(
            evaluations.evaluate_model,
        )
        self.rescore = async_to_raw_response_wrapper(
            evaluations.rescore,
        )
        self.status = async_to_raw_response_wrapper(
            evaluations.status,
        )


class EvaluationsResourceWithStreamingResponse:
    def __init__(self, evaluations: EvaluationsResource) -> None:
        self._evaluations = evaluations

        self.evaluate_model = to_streamed_response_wrapper(
            evaluations.evaluate_model,
        )
        self.rescore = to_streamed_response_wrapper(
            evaluations.rescore,
        )
        self.status = to_streamed_response_wrapper(
            evaluations.status,
        )


class AsyncEvaluationsResourceWithStreamingResponse:
    def __init__(self, evaluations: AsyncEvaluationsResource) -> None:
        self._evaluations = evaluations

        self.evaluate_model = async_to_streamed_response_wrapper(
            evaluations.evaluate_model,
        )
        self.rescore = async_to_streamed_response_wrapper(
            evaluations.rescore,
        )
        self.status = async_to_streamed_response_wrapper(
            evaluations.status,
        )
