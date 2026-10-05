# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Union
from datetime import datetime

import httpx

from ..._types import Body, Omit, Query, Headers, NotGiven, SequenceNotStr, omit, not_given
from ..._utils import maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from ..._base_client import make_request_options
from ...types.agents import conversation_chat_params, conversation_spans_params
from ...types.agents.conversation_chat_response import ConversationChatResponse
from ...types.agents.conversation_spans_response import ConversationSpansResponse

__all__ = ["ConversationsResource", "AsyncConversationsResource"]


class ConversationsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ConversationsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return ConversationsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ConversationsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return ConversationsResourceWithStreamingResponse(self)

    def chat(
        self,
        *,
        conversation_id: str,
        project_id: str,
        include_feedback: bool | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ConversationChatResponse:
        """
        Genai Conversation Chat

        Args:
          limit: Maximum number of conversation turns to return.

          offset: Number of most-recent turns to skip. Results are returned in chronological order
              within the selected page.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/agents/conversations/chat",
            body=maybe_transform(
                {
                    "conversation_id": conversation_id,
                    "project_id": project_id,
                    "include_feedback": include_feedback,
                    "limit": limit,
                    "offset": offset,
                },
                conversation_chat_params.ConversationChatParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ConversationChatResponse,
        )

    def spans(
        self,
        *,
        project_id: str,
        conversation_ids: SequenceNotStr[str] | Omit = omit,
        started_after: Union[str, datetime, None] | Omit = omit,
        started_before: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ConversationSpansResponse:
        """
        Genai Conversation Spans

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/agents/conversations/spans",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "conversation_ids": conversation_ids,
                    "started_after": started_after,
                    "started_before": started_before,
                },
                conversation_spans_params.ConversationSpansParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ConversationSpansResponse,
        )


class AsyncConversationsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncConversationsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncConversationsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncConversationsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncConversationsResourceWithStreamingResponse(self)

    async def chat(
        self,
        *,
        conversation_id: str,
        project_id: str,
        include_feedback: bool | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ConversationChatResponse:
        """
        Genai Conversation Chat

        Args:
          limit: Maximum number of conversation turns to return.

          offset: Number of most-recent turns to skip. Results are returned in chronological order
              within the selected page.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/agents/conversations/chat",
            body=await async_maybe_transform(
                {
                    "conversation_id": conversation_id,
                    "project_id": project_id,
                    "include_feedback": include_feedback,
                    "limit": limit,
                    "offset": offset,
                },
                conversation_chat_params.ConversationChatParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ConversationChatResponse,
        )

    async def spans(
        self,
        *,
        project_id: str,
        conversation_ids: SequenceNotStr[str] | Omit = omit,
        started_after: Union[str, datetime, None] | Omit = omit,
        started_before: Union[str, datetime, None] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ConversationSpansResponse:
        """
        Genai Conversation Spans

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/agents/conversations/spans",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "conversation_ids": conversation_ids,
                    "started_after": started_after,
                    "started_before": started_before,
                },
                conversation_spans_params.ConversationSpansParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ConversationSpansResponse,
        )


class ConversationsResourceWithRawResponse:
    def __init__(self, conversations: ConversationsResource) -> None:
        self._conversations = conversations

        self.chat = to_raw_response_wrapper(
            conversations.chat,
        )
        self.spans = to_raw_response_wrapper(
            conversations.spans,
        )


class AsyncConversationsResourceWithRawResponse:
    def __init__(self, conversations: AsyncConversationsResource) -> None:
        self._conversations = conversations

        self.chat = async_to_raw_response_wrapper(
            conversations.chat,
        )
        self.spans = async_to_raw_response_wrapper(
            conversations.spans,
        )


class ConversationsResourceWithStreamingResponse:
    def __init__(self, conversations: ConversationsResource) -> None:
        self._conversations = conversations

        self.chat = to_streamed_response_wrapper(
            conversations.chat,
        )
        self.spans = to_streamed_response_wrapper(
            conversations.spans,
        )


class AsyncConversationsResourceWithStreamingResponse:
    def __init__(self, conversations: AsyncConversationsResource) -> None:
        self._conversations = conversations

        self.chat = async_to_streamed_response_wrapper(
            conversations.chat,
        )
        self.spans = async_to_streamed_response_wrapper(
            conversations.spans,
        )
