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
from ...types.projects import ingest_sampling_setting_read_params
from ...types.projects.ingest_sampling_setting_read_response import IngestSamplingSettingReadResponse

__all__ = ["IngestSamplingSettingsResource", "AsyncIngestSamplingSettingsResource"]


class IngestSamplingSettingsResource(SyncAPIResource):
    @cached_property
    def with_raw_response(self) -> IngestSamplingSettingsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return IngestSamplingSettingsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> IngestSamplingSettingsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return IngestSamplingSettingsResourceWithStreamingResponse(self)

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
    ) -> IngestSamplingSettingReadResponse:
        """
        Project Ingest Sampling Settings Read

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/project/ingest_sampling_settings/read",
            body=maybe_transform(
                {"project_id": project_id}, ingest_sampling_setting_read_params.IngestSamplingSettingReadParams
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=IngestSamplingSettingReadResponse,
        )


class AsyncIngestSamplingSettingsResource(AsyncAPIResource):
    @cached_property
    def with_raw_response(self) -> AsyncIngestSamplingSettingsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncIngestSamplingSettingsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncIngestSamplingSettingsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncIngestSamplingSettingsResourceWithStreamingResponse(self)

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
    ) -> IngestSamplingSettingReadResponse:
        """
        Project Ingest Sampling Settings Read

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/project/ingest_sampling_settings/read",
            body=await async_maybe_transform(
                {"project_id": project_id}, ingest_sampling_setting_read_params.IngestSamplingSettingReadParams
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=IngestSamplingSettingReadResponse,
        )


class IngestSamplingSettingsResourceWithRawResponse:
    def __init__(self, ingest_sampling_settings: IngestSamplingSettingsResource) -> None:
        self._ingest_sampling_settings = ingest_sampling_settings

        self.read = to_raw_response_wrapper(
            ingest_sampling_settings.read,
        )


class AsyncIngestSamplingSettingsResourceWithRawResponse:
    def __init__(self, ingest_sampling_settings: AsyncIngestSamplingSettingsResource) -> None:
        self._ingest_sampling_settings = ingest_sampling_settings

        self.read = async_to_raw_response_wrapper(
            ingest_sampling_settings.read,
        )


class IngestSamplingSettingsResourceWithStreamingResponse:
    def __init__(self, ingest_sampling_settings: IngestSamplingSettingsResource) -> None:
        self._ingest_sampling_settings = ingest_sampling_settings

        self.read = to_streamed_response_wrapper(
            ingest_sampling_settings.read,
        )


class AsyncIngestSamplingSettingsResourceWithStreamingResponse:
    def __init__(self, ingest_sampling_settings: AsyncIngestSamplingSettingsResource) -> None:
        self._ingest_sampling_settings = ingest_sampling_settings

        self.read = async_to_streamed_response_wrapper(
            ingest_sampling_settings.read,
        )
