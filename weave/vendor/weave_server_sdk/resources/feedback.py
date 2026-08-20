# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Dict, Iterable, Optional

import httpx

from ..types import (
    feedback_purge_params,
    feedback_query_params,
    feedback_create_params,
    feedback_replace_params,
    feedback_batch_create_params,
)
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
from ..types.feedback_query_response import FeedbackQueryResponse
from ..types.feedback_create_response import FeedbackCreateResponse
from ..types.feedback_replace_response import FeedbackReplaceResponse
from ..types.feedback_batch_create_response import FeedbackBatchCreateResponse

__all__ = ["FeedbackResource", "AsyncFeedbackResource"]


class FeedbackResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> FeedbackResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return FeedbackResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> FeedbackResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return FeedbackResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        feedback_type: str,
        payload: Dict[str, object],
        project_id: str,
        weave_ref: str,
        id: Optional[str] | Omit = omit,
        annotation_ref: Optional[str] | Omit = omit,
        call_ref: Optional[str] | Omit = omit,
        creator: Optional[str] | Omit = omit,
        queue_id: Optional[str] | Omit = omit,
        runnable_ref: Optional[str] | Omit = omit,
        scorer_rating_confidences: Dict[str, float] | Omit = omit,
        scorer_rating_reasons: Dict[str, str] | Omit = omit,
        scorer_ratings: Dict[str, float] | Omit = omit,
        scorer_tag_confidences: Dict[str, float] | Omit = omit,
        scorer_tag_reasons: Dict[str, str] | Omit = omit,
        scorer_tags: SequenceNotStr[str] | Omit = omit,
        scorer_trace_id: str | Omit = omit,
        span_agent_name: str | Omit = omit,
        span_agent_version: str | Omit = omit,
        span_conversation_id: str | Omit = omit,
        span_status_code: str | Omit = omit,
        span_trace_id: str | Omit = omit,
        trigger_ref: Optional[str] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackCreateResponse:
        """
        Add feedback to a call or object.

        Args:
          id: If provided by the client, this ID will be used for the feedback row instead of
              a server-generated one.

          queue_id: The annotation queue ID this feedback was created from. References
              annotation_queues.id. NULL when feedback is created outside of queues.

          scorer_rating_confidences: confidence (0-1) per rating, keyed by rating name

          scorer_rating_reasons: reason text per rating, keyed by rating name

          scorer_ratings: numeric ratings (0-1) keyed by rating name

          scorer_tag_confidences: confidence (0-1) per tag, keyed by tag name

          scorer_tag_reasons: reason text per tag, keyed by tag name

          scorer_tags: Tags applied to the ref by a scorer

          scorer_trace_id: Trace of the scorer (judge) invocation that produced this feedback
              (spans.trace_id of the judge call). Distinct from span_trace_id, which is the
              scored turn. Lets signals price the invocation off the judge span without
              joining the calls model.

          span_agent_name: Display name of the scored agent (from spans.agent_name)

          span_agent_version: Version of the scored agent (from spans.agent_version)

          span_conversation_id: Conversation the feedback belongs to (from spans.conversation_id)

          span_status_code: Status of the scored turn (from spans.status_code)

          span_trace_id: Turn the feedback belongs to (from spans.trace_id)

          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/feedback/create",
            body=maybe_transform(
                {
                    "feedback_type": feedback_type,
                    "payload": payload,
                    "project_id": project_id,
                    "weave_ref": weave_ref,
                    "id": id,
                    "annotation_ref": annotation_ref,
                    "call_ref": call_ref,
                    "creator": creator,
                    "queue_id": queue_id,
                    "runnable_ref": runnable_ref,
                    "scorer_rating_confidences": scorer_rating_confidences,
                    "scorer_rating_reasons": scorer_rating_reasons,
                    "scorer_ratings": scorer_ratings,
                    "scorer_tag_confidences": scorer_tag_confidences,
                    "scorer_tag_reasons": scorer_tag_reasons,
                    "scorer_tags": scorer_tags,
                    "scorer_trace_id": scorer_trace_id,
                    "span_agent_name": span_agent_name,
                    "span_agent_version": span_agent_version,
                    "span_conversation_id": span_conversation_id,
                    "span_status_code": span_status_code,
                    "span_trace_id": span_trace_id,
                    "trigger_ref": trigger_ref,
                    "wb_user_id": wb_user_id,
                },
                feedback_create_params.FeedbackCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackCreateResponse,
        )

    def batch_create(
        self,
        *,
        batch: Iterable[feedback_batch_create_params.Batch],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackBatchCreateResponse:
        """
        Add multiple feedback items to calls or objects.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/feedback/batch/create",
            body=maybe_transform({"batch": batch}, feedback_batch_create_params.FeedbackBatchCreateParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackBatchCreateResponse,
        )

    def purge(
        self,
        *,
        project_id: str,
        query: feedback_purge_params.Query,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Permanently delete feedback.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/feedback/purge",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "query": query,
                },
                feedback_purge_params.FeedbackPurgeParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def query(
        self,
        *,
        project_id: str,
        fields: Optional[SequenceNotStr[str]] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        query: Optional[feedback_query_params.Query] | Omit = omit,
        sort_by: Optional[Iterable[feedback_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackQueryResponse:
        """
        Query for feedback.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/feedback/query",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "fields": fields,
                    "limit": limit,
                    "offset": offset,
                    "query": query,
                    "sort_by": sort_by,
                },
                feedback_query_params.FeedbackQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackQueryResponse,
        )

    def replace(
        self,
        *,
        feedback_id: str,
        feedback_type: str,
        payload: Dict[str, object],
        project_id: str,
        weave_ref: str,
        id: Optional[str] | Omit = omit,
        annotation_ref: Optional[str] | Omit = omit,
        call_ref: Optional[str] | Omit = omit,
        creator: Optional[str] | Omit = omit,
        queue_id: Optional[str] | Omit = omit,
        runnable_ref: Optional[str] | Omit = omit,
        scorer_rating_confidences: Dict[str, float] | Omit = omit,
        scorer_rating_reasons: Dict[str, str] | Omit = omit,
        scorer_ratings: Dict[str, float] | Omit = omit,
        scorer_tag_confidences: Dict[str, float] | Omit = omit,
        scorer_tag_reasons: Dict[str, str] | Omit = omit,
        scorer_tags: SequenceNotStr[str] | Omit = omit,
        scorer_trace_id: str | Omit = omit,
        span_agent_name: str | Omit = omit,
        span_agent_version: str | Omit = omit,
        span_conversation_id: str | Omit = omit,
        span_status_code: str | Omit = omit,
        span_trace_id: str | Omit = omit,
        trigger_ref: Optional[str] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackReplaceResponse:
        """
        Feedback Replace

        Args:
          id: If provided by the client, this ID will be used for the feedback row instead of
              a server-generated one.

          queue_id: The annotation queue ID this feedback was created from. References
              annotation_queues.id. NULL when feedback is created outside of queues.

          scorer_rating_confidences: confidence (0-1) per rating, keyed by rating name

          scorer_rating_reasons: reason text per rating, keyed by rating name

          scorer_ratings: numeric ratings (0-1) keyed by rating name

          scorer_tag_confidences: confidence (0-1) per tag, keyed by tag name

          scorer_tag_reasons: reason text per tag, keyed by tag name

          scorer_tags: Tags applied to the ref by a scorer

          scorer_trace_id: Trace of the scorer (judge) invocation that produced this feedback
              (spans.trace_id of the judge call). Distinct from span_trace_id, which is the
              scored turn. Lets signals price the invocation off the judge span without
              joining the calls model.

          span_agent_name: Display name of the scored agent (from spans.agent_name)

          span_agent_version: Version of the scored agent (from spans.agent_version)

          span_conversation_id: Conversation the feedback belongs to (from spans.conversation_id)

          span_status_code: Status of the scored turn (from spans.status_code)

          span_trace_id: Turn the feedback belongs to (from spans.trace_id)

          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/feedback/replace",
            body=maybe_transform(
                {
                    "feedback_id": feedback_id,
                    "feedback_type": feedback_type,
                    "payload": payload,
                    "project_id": project_id,
                    "weave_ref": weave_ref,
                    "id": id,
                    "annotation_ref": annotation_ref,
                    "call_ref": call_ref,
                    "creator": creator,
                    "queue_id": queue_id,
                    "runnable_ref": runnable_ref,
                    "scorer_rating_confidences": scorer_rating_confidences,
                    "scorer_rating_reasons": scorer_rating_reasons,
                    "scorer_ratings": scorer_ratings,
                    "scorer_tag_confidences": scorer_tag_confidences,
                    "scorer_tag_reasons": scorer_tag_reasons,
                    "scorer_tags": scorer_tags,
                    "scorer_trace_id": scorer_trace_id,
                    "span_agent_name": span_agent_name,
                    "span_agent_version": span_agent_version,
                    "span_conversation_id": span_conversation_id,
                    "span_status_code": span_status_code,
                    "span_trace_id": span_trace_id,
                    "trigger_ref": trigger_ref,
                    "wb_user_id": wb_user_id,
                },
                feedback_replace_params.FeedbackReplaceParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackReplaceResponse,
        )


class AsyncFeedbackResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncFeedbackResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncFeedbackResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncFeedbackResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncFeedbackResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        feedback_type: str,
        payload: Dict[str, object],
        project_id: str,
        weave_ref: str,
        id: Optional[str] | Omit = omit,
        annotation_ref: Optional[str] | Omit = omit,
        call_ref: Optional[str] | Omit = omit,
        creator: Optional[str] | Omit = omit,
        queue_id: Optional[str] | Omit = omit,
        runnable_ref: Optional[str] | Omit = omit,
        scorer_rating_confidences: Dict[str, float] | Omit = omit,
        scorer_rating_reasons: Dict[str, str] | Omit = omit,
        scorer_ratings: Dict[str, float] | Omit = omit,
        scorer_tag_confidences: Dict[str, float] | Omit = omit,
        scorer_tag_reasons: Dict[str, str] | Omit = omit,
        scorer_tags: SequenceNotStr[str] | Omit = omit,
        scorer_trace_id: str | Omit = omit,
        span_agent_name: str | Omit = omit,
        span_agent_version: str | Omit = omit,
        span_conversation_id: str | Omit = omit,
        span_status_code: str | Omit = omit,
        span_trace_id: str | Omit = omit,
        trigger_ref: Optional[str] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackCreateResponse:
        """
        Add feedback to a call or object.

        Args:
          id: If provided by the client, this ID will be used for the feedback row instead of
              a server-generated one.

          queue_id: The annotation queue ID this feedback was created from. References
              annotation_queues.id. NULL when feedback is created outside of queues.

          scorer_rating_confidences: confidence (0-1) per rating, keyed by rating name

          scorer_rating_reasons: reason text per rating, keyed by rating name

          scorer_ratings: numeric ratings (0-1) keyed by rating name

          scorer_tag_confidences: confidence (0-1) per tag, keyed by tag name

          scorer_tag_reasons: reason text per tag, keyed by tag name

          scorer_tags: Tags applied to the ref by a scorer

          scorer_trace_id: Trace of the scorer (judge) invocation that produced this feedback
              (spans.trace_id of the judge call). Distinct from span_trace_id, which is the
              scored turn. Lets signals price the invocation off the judge span without
              joining the calls model.

          span_agent_name: Display name of the scored agent (from spans.agent_name)

          span_agent_version: Version of the scored agent (from spans.agent_version)

          span_conversation_id: Conversation the feedback belongs to (from spans.conversation_id)

          span_status_code: Status of the scored turn (from spans.status_code)

          span_trace_id: Turn the feedback belongs to (from spans.trace_id)

          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/feedback/create",
            body=await async_maybe_transform(
                {
                    "feedback_type": feedback_type,
                    "payload": payload,
                    "project_id": project_id,
                    "weave_ref": weave_ref,
                    "id": id,
                    "annotation_ref": annotation_ref,
                    "call_ref": call_ref,
                    "creator": creator,
                    "queue_id": queue_id,
                    "runnable_ref": runnable_ref,
                    "scorer_rating_confidences": scorer_rating_confidences,
                    "scorer_rating_reasons": scorer_rating_reasons,
                    "scorer_ratings": scorer_ratings,
                    "scorer_tag_confidences": scorer_tag_confidences,
                    "scorer_tag_reasons": scorer_tag_reasons,
                    "scorer_tags": scorer_tags,
                    "scorer_trace_id": scorer_trace_id,
                    "span_agent_name": span_agent_name,
                    "span_agent_version": span_agent_version,
                    "span_conversation_id": span_conversation_id,
                    "span_status_code": span_status_code,
                    "span_trace_id": span_trace_id,
                    "trigger_ref": trigger_ref,
                    "wb_user_id": wb_user_id,
                },
                feedback_create_params.FeedbackCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackCreateResponse,
        )

    async def batch_create(
        self,
        *,
        batch: Iterable[feedback_batch_create_params.Batch],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackBatchCreateResponse:
        """
        Add multiple feedback items to calls or objects.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/feedback/batch/create",
            body=await async_maybe_transform({"batch": batch}, feedback_batch_create_params.FeedbackBatchCreateParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackBatchCreateResponse,
        )

    async def purge(
        self,
        *,
        project_id: str,
        query: feedback_purge_params.Query,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """
        Permanently delete feedback.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/feedback/purge",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "query": query,
                },
                feedback_purge_params.FeedbackPurgeParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def query(
        self,
        *,
        project_id: str,
        fields: Optional[SequenceNotStr[str]] | Omit = omit,
        limit: Optional[int] | Omit = omit,
        offset: Optional[int] | Omit = omit,
        query: Optional[feedback_query_params.Query] | Omit = omit,
        sort_by: Optional[Iterable[feedback_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackQueryResponse:
        """
        Query for feedback.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/feedback/query",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "fields": fields,
                    "limit": limit,
                    "offset": offset,
                    "query": query,
                    "sort_by": sort_by,
                },
                feedback_query_params.FeedbackQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackQueryResponse,
        )

    async def replace(
        self,
        *,
        feedback_id: str,
        feedback_type: str,
        payload: Dict[str, object],
        project_id: str,
        weave_ref: str,
        id: Optional[str] | Omit = omit,
        annotation_ref: Optional[str] | Omit = omit,
        call_ref: Optional[str] | Omit = omit,
        creator: Optional[str] | Omit = omit,
        queue_id: Optional[str] | Omit = omit,
        runnable_ref: Optional[str] | Omit = omit,
        scorer_rating_confidences: Dict[str, float] | Omit = omit,
        scorer_rating_reasons: Dict[str, str] | Omit = omit,
        scorer_ratings: Dict[str, float] | Omit = omit,
        scorer_tag_confidences: Dict[str, float] | Omit = omit,
        scorer_tag_reasons: Dict[str, str] | Omit = omit,
        scorer_tags: SequenceNotStr[str] | Omit = omit,
        scorer_trace_id: str | Omit = omit,
        span_agent_name: str | Omit = omit,
        span_agent_version: str | Omit = omit,
        span_conversation_id: str | Omit = omit,
        span_status_code: str | Omit = omit,
        span_trace_id: str | Omit = omit,
        trigger_ref: Optional[str] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> FeedbackReplaceResponse:
        """
        Feedback Replace

        Args:
          id: If provided by the client, this ID will be used for the feedback row instead of
              a server-generated one.

          queue_id: The annotation queue ID this feedback was created from. References
              annotation_queues.id. NULL when feedback is created outside of queues.

          scorer_rating_confidences: confidence (0-1) per rating, keyed by rating name

          scorer_rating_reasons: reason text per rating, keyed by rating name

          scorer_ratings: numeric ratings (0-1) keyed by rating name

          scorer_tag_confidences: confidence (0-1) per tag, keyed by tag name

          scorer_tag_reasons: reason text per tag, keyed by tag name

          scorer_tags: Tags applied to the ref by a scorer

          scorer_trace_id: Trace of the scorer (judge) invocation that produced this feedback
              (spans.trace_id of the judge call). Distinct from span_trace_id, which is the
              scored turn. Lets signals price the invocation off the judge span without
              joining the calls model.

          span_agent_name: Display name of the scored agent (from spans.agent_name)

          span_agent_version: Version of the scored agent (from spans.agent_version)

          span_conversation_id: Conversation the feedback belongs to (from spans.conversation_id)

          span_status_code: Status of the scored turn (from spans.status_code)

          span_trace_id: Turn the feedback belongs to (from spans.trace_id)

          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/feedback/replace",
            body=await async_maybe_transform(
                {
                    "feedback_id": feedback_id,
                    "feedback_type": feedback_type,
                    "payload": payload,
                    "project_id": project_id,
                    "weave_ref": weave_ref,
                    "id": id,
                    "annotation_ref": annotation_ref,
                    "call_ref": call_ref,
                    "creator": creator,
                    "queue_id": queue_id,
                    "runnable_ref": runnable_ref,
                    "scorer_rating_confidences": scorer_rating_confidences,
                    "scorer_rating_reasons": scorer_rating_reasons,
                    "scorer_ratings": scorer_ratings,
                    "scorer_tag_confidences": scorer_tag_confidences,
                    "scorer_tag_reasons": scorer_tag_reasons,
                    "scorer_tags": scorer_tags,
                    "scorer_trace_id": scorer_trace_id,
                    "span_agent_name": span_agent_name,
                    "span_agent_version": span_agent_version,
                    "span_conversation_id": span_conversation_id,
                    "span_status_code": span_status_code,
                    "span_trace_id": span_trace_id,
                    "trigger_ref": trigger_ref,
                    "wb_user_id": wb_user_id,
                },
                feedback_replace_params.FeedbackReplaceParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=FeedbackReplaceResponse,
        )


class FeedbackResourceWithRawResponse:
    def __init__(self, feedback: FeedbackResource) -> None:
        self._feedback = feedback

        self.create = to_raw_response_wrapper(
            feedback.create,
        )
        self.batch_create = to_raw_response_wrapper(
            feedback.batch_create,
        )
        self.purge = to_raw_response_wrapper(
            feedback.purge,
        )
        self.query = to_raw_response_wrapper(
            feedback.query,
        )
        self.replace = to_raw_response_wrapper(
            feedback.replace,
        )


class AsyncFeedbackResourceWithRawResponse:
    def __init__(self, feedback: AsyncFeedbackResource) -> None:
        self._feedback = feedback

        self.create = async_to_raw_response_wrapper(
            feedback.create,
        )
        self.batch_create = async_to_raw_response_wrapper(
            feedback.batch_create,
        )
        self.purge = async_to_raw_response_wrapper(
            feedback.purge,
        )
        self.query = async_to_raw_response_wrapper(
            feedback.query,
        )
        self.replace = async_to_raw_response_wrapper(
            feedback.replace,
        )


class FeedbackResourceWithStreamingResponse:
    def __init__(self, feedback: FeedbackResource) -> None:
        self._feedback = feedback

        self.create = to_streamed_response_wrapper(
            feedback.create,
        )
        self.batch_create = to_streamed_response_wrapper(
            feedback.batch_create,
        )
        self.purge = to_streamed_response_wrapper(
            feedback.purge,
        )
        self.query = to_streamed_response_wrapper(
            feedback.query,
        )
        self.replace = to_streamed_response_wrapper(
            feedback.replace,
        )


class AsyncFeedbackResourceWithStreamingResponse:
    def __init__(self, feedback: AsyncFeedbackResource) -> None:
        self._feedback = feedback

        self.create = async_to_streamed_response_wrapper(
            feedback.create,
        )
        self.batch_create = async_to_streamed_response_wrapper(
            feedback.batch_create,
        )
        self.purge = async_to_streamed_response_wrapper(
            feedback.purge,
        )
        self.query = async_to_streamed_response_wrapper(
            feedback.query,
        )
        self.replace = async_to_streamed_response_wrapper(
            feedback.replace,
        )
