# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import httpx

from ..._types import Body, Query, Headers, NotGiven, not_given
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
from ...types.projects import sensitive_data_setting_read_params
from ...types.projects.sensitive_data_setting_read_response import SensitiveDataSettingReadResponse

__all__ = ["SensitiveDataSettingsResource", "AsyncSensitiveDataSettingsResource"]


class SensitiveDataSettingsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> SensitiveDataSettingsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return SensitiveDataSettingsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> SensitiveDataSettingsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return SensitiveDataSettingsResourceWithStreamingResponse(self)

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
    ) -> SensitiveDataSettingReadResponse:
        """
        Read the owning organization's sensitive-data policy for a project.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._get(
            "/project/sensitive_data_settings",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=maybe_transform(
                    {"project_id": project_id}, sensitive_data_setting_read_params.SensitiveDataSettingReadParams
                ),
            ),
            cast_to=SensitiveDataSettingReadResponse,
        )


class AsyncSensitiveDataSettingsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncSensitiveDataSettingsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncSensitiveDataSettingsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncSensitiveDataSettingsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncSensitiveDataSettingsResourceWithStreamingResponse(self)

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
    ) -> SensitiveDataSettingReadResponse:
        """
        Read the owning organization's sensitive-data policy for a project.

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._get(
            "/project/sensitive_data_settings",
            options=make_request_options(
                extra_headers=extra_headers,
                extra_query=extra_query,
                extra_body=extra_body,
                timeout=timeout,
                query=await async_maybe_transform(
                    {"project_id": project_id}, sensitive_data_setting_read_params.SensitiveDataSettingReadParams
                ),
            ),
            cast_to=SensitiveDataSettingReadResponse,
        )


class SensitiveDataSettingsResourceWithRawResponse:
    def __init__(self, sensitive_data_settings: SensitiveDataSettingsResource) -> None:
        self._sensitive_data_settings = sensitive_data_settings

        self.read = to_raw_response_wrapper(
            sensitive_data_settings.read,
        )


class AsyncSensitiveDataSettingsResourceWithRawResponse:
    def __init__(self, sensitive_data_settings: AsyncSensitiveDataSettingsResource) -> None:
        self._sensitive_data_settings = sensitive_data_settings

        self.read = async_to_raw_response_wrapper(
            sensitive_data_settings.read,
        )


class SensitiveDataSettingsResourceWithStreamingResponse:
    def __init__(self, sensitive_data_settings: SensitiveDataSettingsResource) -> None:
        self._sensitive_data_settings = sensitive_data_settings

        self.read = to_streamed_response_wrapper(
            sensitive_data_settings.read,
        )


class AsyncSensitiveDataSettingsResourceWithStreamingResponse:
    def __init__(self, sensitive_data_settings: AsyncSensitiveDataSettingsResource) -> None:
        self._sensitive_data_settings = sensitive_data_settings

        self.read = async_to_streamed_response_wrapper(
            sensitive_data_settings.read,
        )
