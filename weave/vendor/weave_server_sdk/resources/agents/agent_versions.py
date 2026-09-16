# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Iterable, Optional

import httpx

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
from ..._base_client import make_request_options
from ...types.agents import agent_version_query_params
from ...types.agents.agent_version_query_response import AgentVersionQueryResponse

__all__ = ["AgentVersionsResource", "AsyncAgentVersionsResource"]


class AgentVersionsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AgentVersionsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AgentVersionsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AgentVersionsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AgentVersionsResourceWithStreamingResponse(self)

    def query(
        self,
        *,
        agent_name: str,
        project_id: str,
        include_costs: bool | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        sort_by: Optional[Iterable[agent_version_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AgentVersionQueryResponse:
        """
        Genai Agent Versions Query

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/agents/agent-versions/query",
            body=maybe_transform(
                {
                    "agent_name": agent_name,
                    "project_id": project_id,
                    "include_costs": include_costs,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                agent_version_query_params.AgentVersionQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentVersionQueryResponse,
        )


class AsyncAgentVersionsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncAgentVersionsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncAgentVersionsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncAgentVersionsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncAgentVersionsResourceWithStreamingResponse(self)

    async def query(
        self,
        *,
        agent_name: str,
        project_id: str,
        include_costs: bool | Omit = omit,
        limit: int | Omit = omit,
        offset: int | Omit = omit,
        sort_by: Optional[Iterable[agent_version_query_params.SortBy]] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> AgentVersionQueryResponse:
        """
        Genai Agent Versions Query

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/agents/agent-versions/query",
            body=await async_maybe_transform(
                {
                    "agent_name": agent_name,
                    "project_id": project_id,
                    "include_costs": include_costs,
                    "limit": limit,
                    "offset": offset,
                    "sort_by": sort_by,
                },
                agent_version_query_params.AgentVersionQueryParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=AgentVersionQueryResponse,
        )


class AgentVersionsResourceWithRawResponse:
    def __init__(self, agent_versions: AgentVersionsResource) -> None:
        self._agent_versions = agent_versions

        self.query = to_raw_response_wrapper(
            agent_versions.query,
        )


class AsyncAgentVersionsResourceWithRawResponse:
    def __init__(self, agent_versions: AsyncAgentVersionsResource) -> None:
        self._agent_versions = agent_versions

        self.query = async_to_raw_response_wrapper(
            agent_versions.query,
        )


class AgentVersionsResourceWithStreamingResponse:
    def __init__(self, agent_versions: AgentVersionsResource) -> None:
        self._agent_versions = agent_versions

        self.query = to_streamed_response_wrapper(
            agent_versions.query,
        )


class AsyncAgentVersionsResourceWithStreamingResponse:
    def __init__(self, agent_versions: AsyncAgentVersionsResource) -> None:
        self._agent_versions = agent_versions

        self.query = async_to_streamed_response_wrapper(
            agent_versions.query,
        )
