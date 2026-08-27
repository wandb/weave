# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import List, Union, Iterable, Optional
from datetime import datetime
from typing_extensions import Literal

import httpx

from .spans import (
    SpansResource,
    AsyncSpansResource,
    SpansResourceWithRawResponse,
    AsyncSpansResourceWithRawResponse,
    SpansResourceWithStreamingResponse,
    AsyncSpansResourceWithStreamingResponse,
)
from .traces import (
    TracesResource,
    AsyncTracesResource,
    TracesResourceWithRawResponse,
    AsyncTracesResourceWithRawResponse,
    TracesResourceWithStreamingResponse,
    AsyncTracesResourceWithStreamingResponse,
)
from ...types import agent_query_params, agent_search_params
from ..._types import Body, Omit, Query, Headers, NotGiven, omit, not_given
from ..._utils import maybe_transform, async_maybe_transform
from ..._compat import cached_property
from ..._resource import SyncAPIResource, AsyncAPIResource
from ..._response import (
    to_raw_response_wrapper,
    to_streamed_response_wrapper,
    async_to_raw_response_wrapper,
    async_to_streamed_response_wrapper,
)
from .conversations import (
    ConversationsResource,
    AsyncConversationsResource,
    ConversationsResourceWithRawResponse,
    AsyncConversationsResourceWithRawResponse,
    ConversationsResourceWithStreamingResponse,
    AsyncConversationsResourceWithStreamingResponse,
)
from ..._base_client import make_request_options
from .agent_versions import (
    AgentVersionsResource,
    AsyncAgentVersionsResource,
    AgentVersionsResourceWithRawResponse,
    AsyncAgentVersionsResourceWithRawResponse,
    AgentVersionsResourceWithStreamingResponse,
    AsyncAgentVersionsResourceWithStreamingResponse,
)
from ...types.agent_query_response import AgentQueryResponse
from ...types.agent_search_response import AgentSearchResponse

__all__ = ["AgentsResource", "AsyncAgentsResource"]


class AgentsResource(SyncAPIResource):
    @cached_property
    def spans(self) -> SpansResource:
        return SpansResource(self._client)

    @cached_property
    def agent_versions(self) -> AgentVersionsResource:
        return AgentVersionsResource(self._client)

    @cached_property
    def traces(self) -> TracesResource:
        return TracesResource(self._client)

    @cached_property
    def conversations(self) -> ConversationsResource:
        return ConversationsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AgentsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AgentsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AgentsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AgentsResourceWithStreamingResponse(self)

    def query(
        self,
        *,
        project_id: str,
        filters: Optional[agent_query_params.Filters] | Omit = omit,
        include_costs: bool | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        sort_by: Optional[Iterable[agent_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AgentQueryResponse:
        """
        Genai Agents Query

        Args:
          filters: Optional filters for querying agents.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/agents/query",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "filters": filters,
                    "include_costs": include_costs,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                agent_query_params.AgentQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentQueryResponse,
        )

    def search(
        self,
        *,
        project_id: str,
        agent_name: Optional[str] | Omit = omit,
        conversation_id: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        provider_name: Optional[str] | Omit = omit,
        query: str | Omit = omit,
        request_model: Optional[str] | Omit = omit,
        roles: Optional[List[Literal["", "user", "assistant", "system", "tool", "tool_call", "tool_result"]]]
        | Omit = omit,
        started_after: Union[str, datetime, None] | Omit = omit,
        started_before: Union[str, datetime, None] | Omit = omit,
        trace_id: Optional[str] | Omit = omit,
        truncate_content: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AgentSearchResponse:
        """
        Genai Search

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/agents/search",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "agent_name": agent_name,
                    "conversation_id": conversation_id,
                    "limit": limit,
                    "offset": offset,
                    "provider_name": provider_name,
                    "query": query,
                    "request_model": request_model,
                    "roles": roles,
                    "started_after": started_after,
                    "started_before": started_before,
                    "trace_id": trace_id,
                    "truncate_content": truncate_content,
                },
                agent_search_params.AgentSearchParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentSearchResponse,
        )


class AsyncAgentsResource(AsyncAPIResource):
    @cached_property
    def spans(self) -> AsyncSpansResource:
        return AsyncSpansResource(self._client)

    @cached_property
    def agent_versions(self) -> AsyncAgentVersionsResource:
        return AsyncAgentVersionsResource(self._client)

    @cached_property
    def traces(self) -> AsyncTracesResource:
        return AsyncTracesResource(self._client)

    @cached_property
    def conversations(self) -> AsyncConversationsResource:
        return AsyncConversationsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncAgentsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncAgentsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncAgentsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncAgentsResourceWithStreamingResponse(self)

    async def query(
        self,
        *,
        project_id: str,
        filters: Optional[agent_query_params.Filters] | Omit = omit,
        include_costs: bool | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        sort_by: Optional[Iterable[agent_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AgentQueryResponse:
        """
        Genai Agents Query

        Args:
          filters: Optional filters for querying agents.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/agents/query",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "filters": filters,
                    "include_costs": include_costs,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                agent_query_params.AgentQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentQueryResponse,
        )

    async def search(
        self,
        *,
        project_id: str,
        agent_name: Optional[str] | Omit = omit,
        conversation_id: Optional[str] | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        provider_name: Optional[str] | Omit = omit,
        query: str | Omit = omit,
        request_model: Optional[str] | Omit = omit,
        roles: Optional[List[Literal["", "user", "assistant", "system", "tool", "tool_call", "tool_result"]]]
        | Omit = omit,
        started_after: Union[str, datetime, None] | Omit = omit,
        started_before: Union[str, datetime, None] | Omit = omit,
        trace_id: Optional[str] | Omit = omit,
        truncate_content: bool | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AgentSearchResponse:
        """
        Genai Search

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/agents/search",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "agent_name": agent_name,
                    "conversation_id": conversation_id,
                    "limit": limit,
                    "offset": offset,
                    "provider_name": provider_name,
                    "query": query,
                    "request_model": request_model,
                    "roles": roles,
                    "started_after": started_after,
                    "started_before": started_before,
                    "trace_id": trace_id,
                    "truncate_content": truncate_content,
                },
                agent_search_params.AgentSearchParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentSearchResponse,
        )


class AgentsResourceWithRawResponse:
    def __init__(self, agents: AgentsResource) -> None:
        self._agents = agents

        self.query = to_raw_response_wrapper(
            agents.query,
        )
        self.search = to_raw_response_wrapper(
            agents.search,
        )

    @cached_property
    def spans(self) -> SpansResourceWithRawResponse:
        return SpansResourceWithRawResponse(self._agents.spans)

    @cached_property
    def agent_versions(self) -> AgentVersionsResourceWithRawResponse:
        return AgentVersionsResourceWithRawResponse(self._agents.agent_versions)

    @cached_property
    def traces(self) -> TracesResourceWithRawResponse:
        return TracesResourceWithRawResponse(self._agents.traces)

    @cached_property
    def conversations(self) -> ConversationsResourceWithRawResponse:
        return ConversationsResourceWithRawResponse(self._agents.conversations)


class AsyncAgentsResourceWithRawResponse:
    def __init__(self, agents: AsyncAgentsResource) -> None:
        self._agents = agents

        self.query = async_to_raw_response_wrapper(
            agents.query,
        )
        self.search = async_to_raw_response_wrapper(
            agents.search,
        )

    @cached_property
    def spans(self) -> AsyncSpansResourceWithRawResponse:
        return AsyncSpansResourceWithRawResponse(self._agents.spans)

    @cached_property
    def agent_versions(self) -> AsyncAgentVersionsResourceWithRawResponse:
        return AsyncAgentVersionsResourceWithRawResponse(self._agents.agent_versions)

    @cached_property
    def traces(self) -> AsyncTracesResourceWithRawResponse:
        return AsyncTracesResourceWithRawResponse(self._agents.traces)

    @cached_property
    def conversations(self) -> AsyncConversationsResourceWithRawResponse:
        return AsyncConversationsResourceWithRawResponse(self._agents.conversations)


class AgentsResourceWithStreamingResponse:
    def __init__(self, agents: AgentsResource) -> None:
        self._agents = agents

        self.query = to_streamed_response_wrapper(
            agents.query,
        )
        self.search = to_streamed_response_wrapper(
            agents.search,
        )

    @cached_property
    def spans(self) -> SpansResourceWithStreamingResponse:
        return SpansResourceWithStreamingResponse(self._agents.spans)

    @cached_property
    def agent_versions(self) -> AgentVersionsResourceWithStreamingResponse:
        return AgentVersionsResourceWithStreamingResponse(self._agents.agent_versions)

    @cached_property
    def traces(self) -> TracesResourceWithStreamingResponse:
        return TracesResourceWithStreamingResponse(self._agents.traces)

    @cached_property
    def conversations(self) -> ConversationsResourceWithStreamingResponse:
        return ConversationsResourceWithStreamingResponse(self._agents.conversations)


class AsyncAgentsResourceWithStreamingResponse:
    def __init__(self, agents: AsyncAgentsResource) -> None:
        self._agents = agents

        self.query = async_to_streamed_response_wrapper(
            agents.query,
        )
        self.search = async_to_streamed_response_wrapper(
            agents.search,
        )

    @cached_property
    def spans(self) -> AsyncSpansResourceWithStreamingResponse:
        return AsyncSpansResourceWithStreamingResponse(self._agents.spans)

    @cached_property
    def agent_versions(self) -> AsyncAgentVersionsResourceWithStreamingResponse:
        return AsyncAgentVersionsResourceWithStreamingResponse(self._agents.agent_versions)

    @cached_property
    def traces(self) -> AsyncTracesResourceWithStreamingResponse:
        return AsyncTracesResourceWithStreamingResponse(self._agents.traces)

    @cached_property
    def conversations(self) -> AsyncConversationsResourceWithStreamingResponse:
        return AsyncConversationsResourceWithStreamingResponse(self._agents.conversations)
