# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

from typing import Optional

import httpx

from ...types import project_stats_params
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
from .ttl_settings import (
    TtlSettingsResource,
    AsyncTtlSettingsResource,
    TtlSettingsResourceWithRawResponse,
    AsyncTtlSettingsResourceWithRawResponse,
    TtlSettingsResourceWithStreamingResponse,
    AsyncTtlSettingsResourceWithStreamingResponse,
)
from ..._base_client import make_request_options
from .sensitive_data_settings import (
    SensitiveDataSettingsResource,
    AsyncSensitiveDataSettingsResource,
    SensitiveDataSettingsResourceWithRawResponse,
    AsyncSensitiveDataSettingsResourceWithRawResponse,
    SensitiveDataSettingsResourceWithStreamingResponse,
    AsyncSensitiveDataSettingsResourceWithStreamingResponse,
)
from .ingest_sampling_settings import (
    IngestSamplingSettingsResource,
    AsyncIngestSamplingSettingsResource,
    IngestSamplingSettingsResourceWithRawResponse,
    AsyncIngestSamplingSettingsResourceWithRawResponse,
    IngestSamplingSettingsResourceWithStreamingResponse,
    AsyncIngestSamplingSettingsResourceWithStreamingResponse,
)
from ...types.project_stats_response import ProjectStatsResponse

__all__ = ["ProjectsResource", "AsyncProjectsResource"]


class ProjectsResource(SyncAPIResource):
    @cached_property
    def ttl_settings(self) -> TtlSettingsResource:
        return TtlSettingsResource(self._client)

    @cached_property
    def ingest_sampling_settings(self) -> IngestSamplingSettingsResource:
        return IngestSamplingSettingsResource(self._client)

    @cached_property
    def sensitive_data_settings(self) -> SensitiveDataSettingsResource:
        return SensitiveDataSettingsResource(self._client)

    @cached_property
    def with_raw_response(self) -> ProjectsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return ProjectsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> ProjectsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return ProjectsResourceWithStreamingResponse(self)

    def stats(
        self,
        *,
        project_id: str,
        include_file_storage_size: Optional[bool] | Omit = omit,
        include_object_storage_size: Optional[bool] | Omit = omit,
        include_table_storage_size: Optional[bool] | Omit = omit,
        include_trace_storage_size: Optional[bool] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ProjectStatsResponse:
        """
        Project Stats

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return self._post(
            "/project/stats",
            body=maybe_transform(
                {
                    "project_id": project_id,
                    "include_file_storage_size": include_file_storage_size,
                    "include_object_storage_size": include_object_storage_size,
                    "include_table_storage_size": include_table_storage_size,
                    "include_trace_storage_size": include_trace_storage_size,
                },
                project_stats_params.ProjectStatsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ProjectStatsResponse,
        )


class AsyncProjectsResource(AsyncAPIResource):
    @cached_property
    def ttl_settings(self) -> AsyncTtlSettingsResource:
        return AsyncTtlSettingsResource(self._client)

    @cached_property
    def ingest_sampling_settings(self) -> AsyncIngestSamplingSettingsResource:
        return AsyncIngestSamplingSettingsResource(self._client)

    @cached_property
    def sensitive_data_settings(self) -> AsyncSensitiveDataSettingsResource:
        return AsyncSensitiveDataSettingsResource(self._client)

    @cached_property
    def with_raw_response(self) -> AsyncProjectsResourceWithRawResponse:
        """
        This property can be used as a prefix for any HTTP method call to return
        the raw response object instead of the parsed content.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#accessing-raw-response-data-eg-headers
        """
        return AsyncProjectsResourceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncProjectsResourceWithStreamingResponse:
        """
        An alternative to `.with_raw_response` that doesn't eagerly read the response body.

        For more information, see https://www.github.com/stainless-sdks/weave trace-python#with_streaming_response
        """
        return AsyncProjectsResourceWithStreamingResponse(self)

    async def stats(
        self,
        *,
        project_id: str,
        include_file_storage_size: Optional[bool] | Omit = omit,
        include_object_storage_size: Optional[bool] | Omit = omit,
        include_table_storage_size: Optional[bool] | Omit = omit,
        include_trace_storage_size: Optional[bool] | Omit = omit,
        # Use the following arguments if you need to pass additional parameters to the API that aren't available via kwargs.
        # The extra values given here take precedence over values defined on the client or passed to this method.
        extra_headers: Headers | None = None,
        extra_query: Query | None = None,
        extra_body: Body | None = None,
        timeout: float | httpx.Timeout | None | NotGiven = not_given,
    ) -> ProjectStatsResponse:
        """
        Project Stats

        Args:
          extra_headers: Send extra headers

          extra_query: Add additional query parameters to the request

          extra_body: Add additional JSON properties to the request

          timeout: Override the client-level default timeout for this request, in seconds
        """
        return await self._post(
            "/project/stats",
            body=await async_maybe_transform(
                {
                    "project_id": project_id,
                    "include_file_storage_size": include_file_storage_size,
                    "include_object_storage_size": include_object_storage_size,
                    "include_table_storage_size": include_table_storage_size,
                    "include_trace_storage_size": include_trace_storage_size,
                },
                project_stats_params.ProjectStatsParams,
            ),
            options=make_request_options(
                extra_headers=extra_headers, extra_query=extra_query, extra_body=extra_body, timeout=timeout
            ),
            cast_to=ProjectStatsResponse,
        )


class ProjectsResourceWithRawResponse:
    def __init__(self, projects: ProjectsResource) -> None:
        self._projects = projects

        self.stats = to_raw_response_wrapper(
            projects.stats,
        )

    @cached_property
    def ttl_settings(self) -> TtlSettingsResourceWithRawResponse:
        return TtlSettingsResourceWithRawResponse(self._projects.ttl_settings)

    @cached_property
    def ingest_sampling_settings(self) -> IngestSamplingSettingsResourceWithRawResponse:
        return IngestSamplingSettingsResourceWithRawResponse(self._projects.ingest_sampling_settings)

    @cached_property
    def sensitive_data_settings(self) -> SensitiveDataSettingsResourceWithRawResponse:
        return SensitiveDataSettingsResourceWithRawResponse(self._projects.sensitive_data_settings)


class AsyncProjectsResourceWithRawResponse:
    def __init__(self, projects: AsyncProjectsResource) -> None:
        self._projects = projects

        self.stats = async_to_raw_response_wrapper(
            projects.stats,
        )

    @cached_property
    def ttl_settings(self) -> AsyncTtlSettingsResourceWithRawResponse:
        return AsyncTtlSettingsResourceWithRawResponse(self._projects.ttl_settings)

    @cached_property
    def ingest_sampling_settings(self) -> AsyncIngestSamplingSettingsResourceWithRawResponse:
        return AsyncIngestSamplingSettingsResourceWithRawResponse(self._projects.ingest_sampling_settings)

    @cached_property
    def sensitive_data_settings(self) -> AsyncSensitiveDataSettingsResourceWithRawResponse:
        return AsyncSensitiveDataSettingsResourceWithRawResponse(self._projects.sensitive_data_settings)


class ProjectsResourceWithStreamingResponse:
    def __init__(self, projects: ProjectsResource) -> None:
        self._projects = projects

        self.stats = to_streamed_response_wrapper(
            projects.stats,
        )

    @cached_property
    def ttl_settings(self) -> TtlSettingsResourceWithStreamingResponse:
        return TtlSettingsResourceWithStreamingResponse(self._projects.ttl_settings)

    @cached_property
    def ingest_sampling_settings(self) -> IngestSamplingSettingsResourceWithStreamingResponse:
        return IngestSamplingSettingsResourceWithStreamingResponse(self._projects.ingest_sampling_settings)

    @cached_property
    def sensitive_data_settings(self) -> SensitiveDataSettingsResourceWithStreamingResponse:
        return SensitiveDataSettingsResourceWithStreamingResponse(self._projects.sensitive_data_settings)


class AsyncProjectsResourceWithStreamingResponse:
    def __init__(self, projects: AsyncProjectsResource) -> None:
        self._projects = projects

        self.stats = async_to_streamed_response_wrapper(
            projects.stats,
        )

    @cached_property
    def ttl_settings(self) -> AsyncTtlSettingsResourceWithStreamingResponse:
        return AsyncTtlSettingsResourceWithStreamingResponse(self._projects.ttl_settings)

    @cached_property
    def ingest_sampling_settings(self) -> AsyncIngestSamplingSettingsResourceWithStreamingResponse:
        return AsyncIngestSamplingSettingsResourceWithStreamingResponse(self._projects.ingest_sampling_settings)

    @cached_property
    def sensitive_data_settings(self) -> AsyncSensitiveDataSettingsResourceWithStreamingResponse:
        return AsyncSensitiveDataSettingsResourceWithStreamingResponse(self._projects.sensitive_data_settings)
