# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import httpx

from ..types import service_projects_info_params
from .._types import Body, Query, Headers, NotGiven, SequenceNotStr, not_given
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
from ..types.server_info_res import ServerInfoRes
from ..types.service_projects_info_response import ServiceProjectsInfoResponse

__all__ = ["ServicesResource", "AsyncServicesResource"]


class ServicesResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> ServicesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return ServicesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ServicesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return ServicesResourceWithStreamingResponse(self)

    def health_check(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Read Root (stainless-sync smoke)"""
        return self._get(
            "/health",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    def projects_info(
        self,
        *,
        project_ids: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ServiceProjectsInfoResponse:
        """
        Projects Info

        Args:
          project_ids: External project IDs in 'entity/project' format.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/service/projects_info",
            body=maybe_transform({"project_ids": project_ids}, service_projects_info_params.ServiceProjectsInfoParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ServiceProjectsInfoResponse,
        )

    def server_info(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ServerInfoRes:
        """Server Info"""
        return self._get(
            "/server_info",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ServerInfoRes,
        )


class AsyncServicesResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncServicesResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncServicesResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncServicesResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncServicesResourceWithStreamingResponse(self)

    async def health_check(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> object:
        """Read Root (stainless-sync smoke)"""
        return await self._get(
            "/health",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=object,
        )

    async def projects_info(
        self,
        *,
        project_ids: SequenceNotStr[str],
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ServiceProjectsInfoResponse:
        """
        Projects Info

        Args:
          project_ids: External project IDs in 'entity/project' format.

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/service/projects_info",
            body=await async_maybe_transform(
                {"project_ids": project_ids}, service_projects_info_params.ServiceProjectsInfoParams
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ServiceProjectsInfoResponse,
        )

    async def server_info(
        self,
        *,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ServerInfoRes:
        """Server Info"""
        return await self._get(
            "/server_info",
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ServerInfoRes,
        )


class ServicesResourceWithRawResponse:
    def __init__(self, services: ServicesResource) -> None:
        self._services = services

        self.health_check = to_raw_response_wrapper(
            services.health_check,
        )
        self.projects_info = to_raw_response_wrapper(
            services.projects_info,
        )
        self.server_info = to_raw_response_wrapper(
            services.server_info,
        )


class AsyncServicesResourceWithRawResponse:
    def __init__(self, services: AsyncServicesResource) -> None:
        self._services = services

        self.health_check = async_to_raw_response_wrapper(
            services.health_check,
        )
        self.projects_info = async_to_raw_response_wrapper(
            services.projects_info,
        )
        self.server_info = async_to_raw_response_wrapper(
            services.server_info,
        )


class ServicesResourceWithStreamingResponse:
    def __init__(self, services: ServicesResource) -> None:
        self._services = services

        self.health_check = to_streamed_response_wrapper(
            services.health_check,
        )
        self.projects_info = to_streamed_response_wrapper(
            services.projects_info,
        )
        self.server_info = to_streamed_response_wrapper(
            services.server_info,
        )


class AsyncServicesResourceWithStreamingResponse:
    def __init__(self, services: AsyncServicesResource) -> None:
        self._services = services

        self.health_check = async_to_streamed_response_wrapper(
            services.health_check,
        )
        self.projects_info = async_to_streamed_response_wrapper(
            services.projects_info,
        )
        self.server_info = async_to_streamed_response_wrapper(
            services.server_info,
        )
