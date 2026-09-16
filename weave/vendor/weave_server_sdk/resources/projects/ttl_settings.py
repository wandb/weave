# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional

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
from ...types.projects import ttl_setting_read_params, ttl_setting_update_params
from ...types.projects.ttl_setting_read_response import TtlSettingReadResponse
from ...types.projects.ttl_setting_update_response import TtlSettingUpdateResponse

__all__ = ["TtlSettingsResource", "AsyncTtlSettingsResource"]


class TtlSettingsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> TtlSettingsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return TtlSettingsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> TtlSettingsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return TtlSettingsResourceWithStreamingResponse(self)

    def update(
        self,
        *,
        project_id: str,
        retention_days: Optional[int] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TtlSettingUpdateResponse:
        """
        Project Ttl Settings Update

        Args:
          retention_days: None disables TTL; must be None or >= 1

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/project/ttl_settings/update",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "retention_days": retention_days,
                    "wb_user_id": wb_user_id,
                },
                ttl_setting_update_params.TtlSettingUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TtlSettingUpdateResponse,
        )

    def read(
        self,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TtlSettingReadResponse:
        """
        Project Ttl Settings Read

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/project/ttl_settings/read",
            body=maybe_transform({"project_id": project_id}, ttl_setting_read_params.TtlSettingReadParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TtlSettingReadResponse,
        )


class AsyncTtlSettingsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncTtlSettingsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncTtlSettingsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncTtlSettingsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncTtlSettingsResourceWithStreamingResponse(self)

    async def update(
        self,
        *,
        project_id: str,
        retention_days: Optional[int] | Omit = omit,
        wb_user_id: Optional[str] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TtlSettingUpdateResponse:
        """
        Project Ttl Settings Update

        Args:
          retention_days: None disables TTL; must be None or >= 1

          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/project/ttl_settings/update",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "retention_days": retention_days,
                    "wb_user_id": wb_user_id,
                },
                ttl_setting_update_params.TtlSettingUpdateParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TtlSettingUpdateResponse,
        )

    async def read(
        self,
        *,
        project_id: str,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> TtlSettingReadResponse:
        """
        Project Ttl Settings Read

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/project/ttl_settings/read",
            body=await async_maybe_transform({"project_id": project_id}, ttl_setting_read_params.TtlSettingReadParams),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=TtlSettingReadResponse,
        )


class TtlSettingsResourceWithRawResponse:
    def __init__(self, ttl_settings: TtlSettingsResource) -> None:
        self._ttl_settings = ttl_settings

        self.update = to_raw_response_wrapper(
            ttl_settings.update,
        )
        self.read = to_raw_response_wrapper(
            ttl_settings.read,
        )


class AsyncTtlSettingsResourceWithRawResponse:
    def __init__(self, ttl_settings: AsyncTtlSettingsResource) -> None:
        self._ttl_settings = ttl_settings

        self.update = async_to_raw_response_wrapper(
            ttl_settings.update,
        )
        self.read = async_to_raw_response_wrapper(
            ttl_settings.read,
        )


class TtlSettingsResourceWithStreamingResponse:
    def __init__(self, ttl_settings: TtlSettingsResource) -> None:
        self._ttl_settings = ttl_settings

        self.update = to_streamed_response_wrapper(
            ttl_settings.update,
        )
        self.read = to_streamed_response_wrapper(
            ttl_settings.read,
        )


class AsyncTtlSettingsResourceWithStreamingResponse:
    def __init__(self, ttl_settings: AsyncTtlSettingsResource) -> None:
        self._ttl_settings = ttl_settings

        self.update = async_to_streamed_response_wrapper(
            ttl_settings.update,
        )
        self.read = async_to_streamed_response_wrapper(
            ttl_settings.read,
        )
