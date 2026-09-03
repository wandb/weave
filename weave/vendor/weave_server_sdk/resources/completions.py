# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional

import httpx

from ..types import completion_create_params
from .._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
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
from ..types.completion_create_response import CompletionCreateResponse

__all__ = ["CompletionsResource", "AsyncCompletionsResource"]


class CompletionsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> CompletionsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return CompletionsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> CompletionsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return CompletionsResourceWithStreamingResponse(self)

    def create(
        self,
        *,
        inputs: completion_create_params.Inputs,
        project_id: str,
        conversation_id: Optional[str] | Omit = omit,
        conversation_name: Optional[str] | Omit = omit,
        parent_id: Optional[str] | Omit = omit,
        source: Optional[str] | Omit = omit,
        trace_id: Optional[str] | Omit = omit,
        track_llm_call: Optional[bool] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CompletionCreateResponse:
        """
        Completions Create

        Args:
          conversation_id: Conversation ID to group related completions into a multi-turn conversation

          conversation_name: Human-readable conversation name

          parent_id: Parent call ID to nest this LLM call under

          source: Source of the completion request (e.g. 'playground', 'signals')

          trace_id: Trace ID to use for the LLM call (for nesting under a parent)

          track_llm_call: Whether to track this LLM call in the trace server

          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/completions/create",
            body=maybe_transform(
                {
                    "inputs": inputs,
                    "project_id": project_id,
                    "conversation_id": conversation_id,
                    "conversation_name": conversation_name,
                    "parent_id": parent_id,
                    "source": source,
                    "trace_id": trace_id,
                    "track_llm_call": track_llm_call,
                    "wb_user_id": wb_user_id,
                },
                completion_create_params.CompletionCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CompletionCreateResponse,
        )


class AsyncCompletionsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncCompletionsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncCompletionsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncCompletionsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncCompletionsResourceWithStreamingResponse(self)

    async def create(
        self,
        *,
        inputs: completion_create_params.Inputs,
        project_id: str,
        conversation_id: Optional[str] | Omit = omit,
        conversation_name: Optional[str] | Omit = omit,
        parent_id: Optional[str] | Omit = omit,
        source: Optional[str] | Omit = omit,
        trace_id: Optional[str] | Omit = omit,
        track_llm_call: Optional[bool] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> CompletionCreateResponse:
        """
        Completions Create

        Args:
          conversation_id: Conversation ID to group related completions into a multi-turn conversation

          conversation_name: Human-readable conversation name

          parent_id: Parent call ID to nest this LLM call under

          source: Source of the completion request (e.g. 'playground', 'signals')

          trace_id: Trace ID to use for the LLM call (for nesting under a parent)

          track_llm_call: Whether to track this LLM call in the trace server

          wb_user_id: Do not set directly. Server will automatically populate this field.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/completions/create",
            body=await async_maybe_transform(
                {
                    "inputs": inputs,
                    "project_id": project_id,
                    "conversation_id": conversation_id,
                    "conversation_name": conversation_name,
                    "parent_id": parent_id,
                    "source": source,
                    "trace_id": trace_id,
                    "track_llm_call": track_llm_call,
                    "wb_user_id": wb_user_id,
                },
                completion_create_params.CompletionCreateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=CompletionCreateResponse,
        )


class CompletionsResourceWithRawResponse:
    def __init__(self, completions: CompletionsResource) -> None:
        self._completions = completions

        self.create = to_raw_response_wrapper(
            completions.create,
        )


class AsyncCompletionsResourceWithRawResponse:
    def __init__(self, completions: AsyncCompletionsResource) -> None:
        self._completions = completions

        self.create = async_to_raw_response_wrapper(
            completions.create,
        )


class CompletionsResourceWithStreamingResponse:
    def __init__(self, completions: CompletionsResource) -> None:
        self._completions = completions

        self.create = to_streamed_response_wrapper(
            completions.create,
        )


class AsyncCompletionsResourceWithStreamingResponse:
    def __init__(self, completions: AsyncCompletionsResource) -> None:
        self._completions = completions

        self.create = async_to_streamed_response_wrapper(
            completions.create,
        )
