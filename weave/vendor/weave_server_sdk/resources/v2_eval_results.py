# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional
from typing_extensions import Literal

import httpx

from ..types import v2_eval_result_query_params
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
from ..types.v2_eval_result_query_response import V2EvalResultQueryResponse

__all__ = ["V2EvalResultsResource", "AsyncV2EvalResultsResource"]


class V2EvalResultsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> V2EvalResultsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return V2EvalResultsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> V2EvalResultsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return V2EvalResultsResourceWithStreamingResponse(self)

    def query(
        self,
        project: str,
        *,
        entity: str,
        evaluation_call_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        evaluation_run_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        filter_logic_operator: Literal["and", "or"] | Omit = omit,
        filters: Optional[Iterable[v2_eval_result_query_params.Filter]] | Omit = omit,
        include_costs: bool | Omit = omit,
        include_predict_and_score_children: bool | Omit = omit,
        include_raw_data_rows: bool | Omit = omit,
        include_rows: bool | Omit = omit,
        include_summary: bool | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: int | Omit = omit,
        require_intersection: bool | Omit = omit,
        resolve_row_refs: bool | Omit = omit,
        sort_by: Optional[Iterable[v2_eval_result_query_params.SortBy]] | Omit = omit,
        summary_require_intersection: Optional[bool] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvalResultQueryResponse:
        """
        Read grouped evaluation result rows for one or more evaluations.

        Args:
          evaluation_call_ids: Evaluation root call IDs to include.

          evaluation_run_ids: Alias for evaluation call IDs from the Evaluation Runs API.

          filter_logic_operator: How to combine filters across evaluations: 'and' (Match All - row must match in
              ALL evals) or 'or' (Match Any - row must match in ANY eval). Defaults to 'or'
              (Match Any).

          filters: Filters applied to grouped rows. Multiple filters are AND'd together.

          include_costs: When true, price each trial's predict call so rows and summary report
              predict-only cost (`total_cost` / `predict_total_cost`); scorer costs are
              excluded. Opt-in: other callers skip the cost computation.

          include_predict_and_score_children: When true (default), fetch child calls (predict/score) of each predict_and_score
              call to populate predict_call_id, scorer_call_ids, and more precise
              latency/token data. When false, these fields are derived from the
              predict_and_score call itself (predict_call_id and scorer_call_ids will be
              null/empty).

          include_raw_data_rows: When true, populate raw_data_row on each result row. Inline rows are returned as
              their dict value; dataset-referenced rows are returned as the ref string unless
              resolve_row_refs is also true.

          include_rows: When true, include grouped row/trial data in `rows` and compute `total_rows` for
              the requested row-level view.

          include_summary: When true, include aggregated scorer/evaluation summary data in `summary`.

          limit: Optional row-level page size applied after grouping and intersection.

          offset: Optional row-level page offset applied after grouping and intersection.

          require_intersection: When true, only include rows present in all requested evaluations.

          resolve_row_refs: When true (requires include_raw_data_rows=True), resolve dataset-row reference
              strings to actual row data via a table lookup. When false, dataset-row refs are
              returned as-is.

          sort_by: Sort specification for result rows. Supported field prefixes: scores.<name>,
              inputs.<path>, outputs.<path>. When null, rows are sorted by row_digest ASC.

          summary_require_intersection: Optional intersection behavior for the summary section. When null, the value of
              `require_intersection` is used.

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
            path_template("/v2/{entity}/{project}/eval_results/query", entity=entity, project=project),
            body=maybe_transform(
                {
                    "evaluation_call_ids": evaluation_call_ids,
                    "evaluation_run_ids": evaluation_run_ids,
                    "filter_logic_operator": filter_logic_operator,
                    "filters": filters,
                    "include_costs": include_costs,
                    "include_predict_and_score_children": include_predict_and_score_children,
                    "include_raw_data_rows": include_raw_data_rows,
                    "include_rows": include_rows,
                    "include_summary": include_summary,
                    "limit": limit,
                    "offset": offset,
                    "require_intersection": require_intersection,
                    "resolve_row_refs": resolve_row_refs,
                    "sort_by": sort_by,
                    "summary_require_intersection": summary_require_intersection,
                },
                v2_eval_result_query_params.V2EvalResultQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvalResultQueryResponse,
        )


class AsyncV2EvalResultsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncV2EvalResultsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncV2EvalResultsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncV2EvalResultsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncV2EvalResultsResourceWithStreamingResponse(self)

    async def query(
        self,
        project: str,
        *,
        entity: str,
        evaluation_call_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        evaluation_run_ids: Optional[SequenceNotStr[str]] | Omit = omit,
        filter_logic_operator: Literal["and", "or"] | Omit = omit,
        filters: Optional[Iterable[v2_eval_result_query_params.Filter]] | Omit = omit,
        include_costs: bool | Omit = omit,
        include_predict_and_score_children: bool | Omit = omit,
        include_raw_data_rows: bool | Omit = omit,
        include_rows: bool | Omit = omit,
        include_summary: bool | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: int | Omit = omit,
        require_intersection: bool | Omit = omit,
        resolve_row_refs: bool | Omit = omit,
        sort_by: Optional[Iterable[v2_eval_result_query_params.SortBy]] | Omit = omit,
        summary_require_intersection: Optional[bool] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> V2EvalResultQueryResponse:
        """
        Read grouped evaluation result rows for one or more evaluations.

        Args:
          evaluation_call_ids: Evaluation root call IDs to include.

          evaluation_run_ids: Alias for evaluation call IDs from the Evaluation Runs API.

          filter_logic_operator: How to combine filters across evaluations: 'and' (Match All - row must match in
              ALL evals) or 'or' (Match Any - row must match in ANY eval). Defaults to 'or'
              (Match Any).

          filters: Filters applied to grouped rows. Multiple filters are AND'd together.

          include_costs: When true, price each trial's predict call so rows and summary report
              predict-only cost (`total_cost` / `predict_total_cost`); scorer costs are
              excluded. Opt-in: other callers skip the cost computation.

          include_predict_and_score_children: When true (default), fetch child calls (predict/score) of each predict_and_score
              call to populate predict_call_id, scorer_call_ids, and more precise
              latency/token data. When false, these fields are derived from the
              predict_and_score call itself (predict_call_id and scorer_call_ids will be
              null/empty).

          include_raw_data_rows: When true, populate raw_data_row on each result row. Inline rows are returned as
              their dict value; dataset-referenced rows are returned as the ref string unless
              resolve_row_refs is also true.

          include_rows: When true, include grouped row/trial data in `rows` and compute `total_rows` for
              the requested row-level view.

          include_summary: When true, include aggregated scorer/evaluation summary data in `summary`.

          limit: Optional row-level page size applied after grouping and intersection.

          offset: Optional row-level page offset applied after grouping and intersection.

          require_intersection: When true, only include rows present in all requested evaluations.

          resolve_row_refs: When true (requires include_raw_data_rows=True), resolve dataset-row reference
              strings to actual row data via a table lookup. When false, dataset-row refs are
              returned as-is.

          sort_by: Sort specification for result rows. Supported field prefixes: scores.<name>,
              inputs.<path>, outputs.<path>. When null, rows are sorted by row_digest ASC.

          summary_require_intersection: Optional intersection behavior for the summary section. When null, the value of
              `require_intersection` is used.

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
            path_template("/v2/{entity}/{project}/eval_results/query", entity=entity, project=project),
            body=await async_maybe_transform(
                {
                    "evaluation_call_ids": evaluation_call_ids,
                    "evaluation_run_ids": evaluation_run_ids,
                    "filter_logic_operator": filter_logic_operator,
                    "filters": filters,
                    "include_costs": include_costs,
                    "include_predict_and_score_children": include_predict_and_score_children,
                    "include_raw_data_rows": include_raw_data_rows,
                    "include_rows": include_rows,
                    "include_summary": include_summary,
                    "limit": limit,
                    "offset": offset,
                    "require_intersection": require_intersection,
                    "resolve_row_refs": resolve_row_refs,
                    "sort_by": sort_by,
                    "summary_require_intersection": summary_require_intersection,
                },
                v2_eval_result_query_params.V2EvalResultQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=V2EvalResultQueryResponse,
        )


class V2EvalResultsResourceWithRawResponse:
    def __init__(self, v2_eval_results: V2EvalResultsResource) -> None:
        self._v2_eval_results = v2_eval_results

        self.query = to_raw_response_wrapper(
            v2_eval_results.query,
        )


class AsyncV2EvalResultsResourceWithRawResponse:
    def __init__(self, v2_eval_results: AsyncV2EvalResultsResource) -> None:
        self._v2_eval_results = v2_eval_results

        self.query = async_to_raw_response_wrapper(
            v2_eval_results.query,
        )


class V2EvalResultsResourceWithStreamingResponse:
    def __init__(self, v2_eval_results: V2EvalResultsResource) -> None:
        self._v2_eval_results = v2_eval_results

        self.query = to_streamed_response_wrapper(
            v2_eval_results.query,
        )


class AsyncV2EvalResultsResourceWithStreamingResponse:
    def __init__(self, v2_eval_results: AsyncV2EvalResultsResource) -> None:
        self._v2_eval_results = v2_eval_results

        self.query = async_to_streamed_response_wrapper(
            v2_eval_results.query,
        )
