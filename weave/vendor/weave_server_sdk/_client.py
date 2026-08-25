# File generated from our OpenAPI spec by Stainless. See CONTRIBUTING.md for details.

from __future__ import annotations

import os
import base64
from typing import TYPE_CHECKING, Any, Mapping
from typing_extensions import Self, override

import httpx

from . import _exceptions
from ._qs import Querystring
from ._types import (
    Omit,
    Timeout,
    NotGiven,
    Transport,
    ProxiesTypes,
    RequestOptions,
    not_given,
)
from ._utils import (
    is_given,
    is_mapping_t,
    get_async_library,
)
from ._compat import cached_property
from ._version import __version__
from ._streaming import Stream as Stream, AsyncStream as AsyncStream
from ._exceptions import APIStatusError, WeaveTraceError
from ._base_client import (
    DEFAULT_MAX_RETRIES,
    SyncAPIClient,
    AsyncAPIClient,
)

if TYPE_CHECKING:
    from .resources import (
        otel,
        refs,
        calls,
        costs,
        files,
        trace,
        tables,
        v2_ops,
        objects,
        threads,
        feedback,
        services,
        v2_models,
        v2_scores,
        v2_scorers,
        v2_datasets,
        v2_evaluations,
        v2_predictions,
        v2_evaluation_runs,
    )
    from .resources.otel import OtelResource, AsyncOtelResource
    from .resources.refs import RefsResource, AsyncRefsResource
    from .resources.calls import CallsResource, AsyncCallsResource
    from .resources.costs import CostsResource, AsyncCostsResource
    from .resources.files import FilesResource, AsyncFilesResource
    from .resources.trace import TraceResource, AsyncTraceResource
    from .resources.tables import TablesResource, AsyncTablesResource
    from .resources.v2_ops import V2OpsResource, AsyncV2OpsResource
    from .resources.threads import ThreadsResource, AsyncThreadsResource
    from .resources.feedback import FeedbackResource, AsyncFeedbackResource
    from .resources.services import ServicesResource, AsyncServicesResource
    from .resources.v2_models import V2ModelsResource, AsyncV2ModelsResource
    from .resources.v2_scores import V2ScoresResource, AsyncV2ScoresResource
    from .resources.v2_scorers import V2ScorersResource, AsyncV2ScorersResource
    from .resources.v2_datasets import V2DatasetsResource, AsyncV2DatasetsResource
    from .resources.v2_evaluations import V2EvaluationsResource, AsyncV2EvaluationsResource
    from .resources.v2_predictions import V2PredictionsResource, AsyncV2PredictionsResource
    from .resources.objects.objects import ObjectsResource, AsyncObjectsResource
    from .resources.v2_evaluation_runs import V2EvaluationRunsResource, AsyncV2EvaluationRunsResource

__all__ = [
    "Timeout",
    "Transport",
    "ProxiesTypes",
    "RequestOptions",
    "WeaveTrace",
    "AsyncWeaveTrace",
    "Client",
    "AsyncClient",
]


class WeaveTrace(SyncAPIClient):
    # client options
    username: str
    password: str

    def __init__(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = not_given,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        # Configure a custom httpx client.
        # We provide a `DefaultHttpxClient` class that you can pass to retain the default values we use for `limits`, `timeout` & `follow_redirects`.
        # See the [httpx documentation](https://www.python-httpx.org/api/#client) for more details.
        http_client: httpx.Client | None = None,
        # Enable or disable schema validation for data returned by the API.
        # When enabled an error APIResponseValidationError is raised
        # if the API responds with invalid data for the expected schema.
        #
        # This parameter may be removed or changed in the future.
        # If you rely on this feature, please open a GitHub issue
        # outlining your use-case to help us decide if it should be
        # part of our public interface in the future.
        _strict_response_validation: bool = False,
    ) -> None:
        """Construct a new synchronous WeaveTrace client instance.

        This automatically infers the following arguments from their corresponding environment variables if they are not provided:
        - `username` from `WANDB_USERNAME`
        - `password` from `WANDB_API_KEY`
        """
        if username is None:
            username = os.environ.get("WANDB_USERNAME")
        if username is None:
            raise WeaveTraceError(
                "The username client option must be set either by passing username to the client or by setting the WANDB_USERNAME environment variable"
            )
        self.username = username

        if password is None:
            password = os.environ.get("WANDB_API_KEY")
        if password is None:
            raise WeaveTraceError(
                "The password client option must be set either by passing password to the client or by setting the WANDB_API_KEY environment variable"
            )
        self.password = password

        if base_url is None:
            base_url = os.environ.get("WEAVE_TRACE_BASE_URL")
        if base_url is None:
            base_url = f"https://trace.wandb.ai"

        custom_headers_env = os.environ.get("WEAVE_TRACE_CUSTOM_HEADERS")
        if custom_headers_env is not None:
            parsed: dict[str, str] = {}
            for line in custom_headers_env.split("\n"):
                colon = line.find(":")
                if colon >= 0:
                    parsed[line[:colon].strip()] = line[colon + 1 :].strip()
            default_headers = {**parsed, **(default_headers if is_mapping_t(default_headers) else {})}

        super().__init__(
            version=__version__,
            base_url=base_url,
            max_retries=max_retries,
            timeout=timeout,
            http_client=http_client,
            custom_headers=default_headers,
            custom_query=default_query,
            _strict_response_validation=_strict_response_validation,
        )

    @cached_property
    def services(self) -> ServicesResource:
        from .resources.services import ServicesResource

        return ServicesResource(self)

    @cached_property
    def calls(self) -> CallsResource:
        from .resources.calls import CallsResource

        return CallsResource(self)

    @cached_property
    def objects(self) -> ObjectsResource:
        from .resources.objects import ObjectsResource

        return ObjectsResource(self)

    @cached_property
    def tables(self) -> TablesResource:
        from .resources.tables import TablesResource

        return TablesResource(self)

    @cached_property
    def refs(self) -> RefsResource:
        from .resources.refs import RefsResource

        return RefsResource(self)

    @cached_property
    def files(self) -> FilesResource:
        from .resources.files import FilesResource

        return FilesResource(self)

    @cached_property
    def costs(self) -> CostsResource:
        from .resources.costs import CostsResource

        return CostsResource(self)

    @cached_property
    def feedback(self) -> FeedbackResource:
        from .resources.feedback import FeedbackResource

        return FeedbackResource(self)

    @cached_property
    def otel(self) -> OtelResource:
        from .resources.otel import OtelResource

        return OtelResource(self)

    @cached_property
    def trace(self) -> TraceResource:
        from .resources.trace import TraceResource

        return TraceResource(self)

    @cached_property
    def threads(self) -> ThreadsResource:
        from .resources.threads import ThreadsResource

        return ThreadsResource(self)

    @cached_property
    def v2_ops(self) -> V2OpsResource:
        from .resources.v2_ops import V2OpsResource

        return V2OpsResource(self)

    @cached_property
    def v2_scorers(self) -> V2ScorersResource:
        from .resources.v2_scorers import V2ScorersResource

        return V2ScorersResource(self)

    @cached_property
    def v2_datasets(self) -> V2DatasetsResource:
        from .resources.v2_datasets import V2DatasetsResource

        return V2DatasetsResource(self)

    @cached_property
    def v2_evaluations(self) -> V2EvaluationsResource:
        from .resources.v2_evaluations import V2EvaluationsResource

        return V2EvaluationsResource(self)

    @cached_property
    def v2_models(self) -> V2ModelsResource:
        from .resources.v2_models import V2ModelsResource

        return V2ModelsResource(self)

    @cached_property
    def v2_evaluation_runs(self) -> V2EvaluationRunsResource:
        from .resources.v2_evaluation_runs import V2EvaluationRunsResource

        return V2EvaluationRunsResource(self)

    @cached_property
    def v2_predictions(self) -> V2PredictionsResource:
        from .resources.v2_predictions import V2PredictionsResource

        return V2PredictionsResource(self)

    @cached_property
    def v2_scores(self) -> V2ScoresResource:
        from .resources.v2_scores import V2ScoresResource

        return V2ScoresResource(self)

    @cached_property
    def with_raw_response(self) -> WeaveTraceWithRawResponse:
        return WeaveTraceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> WeaveTraceWithStreamedResponse:
        return WeaveTraceWithStreamedResponse(self)

    @property
    @override
    def qs(self) -> Querystring:
        return Querystring(array_format="comma")

    @property
    @override
    def auth_headers(self) -> dict[str, str]:
        credentials = f"{self.username}:{self.password}".encode("ascii")
        header = f"Basic {base64.b64encode(credentials).decode('ascii')}"
        return {"Authorization": header}

    @property
    @override
    def default_headers(self) -> dict[str, str | Omit]:
        return {
            **super().default_headers,
            "X-Stainless-Async": "false",
            **self._custom_headers,
        }

    def copy(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = not_given,
        http_client: httpx.Client | None = None,
        max_retries: int | NotGiven = not_given,
        default_headers: Mapping[str, str] | None = None,
        set_default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        set_default_query: Mapping[str, object] | None = None,
        _extra_kwargs: Mapping[str, Any] = {},
    ) -> Self:
        """
        Create a new client instance re-using the same options given to the current client with optional overriding.
        """
        if default_headers is not None and set_default_headers is not None:
            raise ValueError("The `default_headers` and `set_default_headers` arguments are mutually exclusive")

        if default_query is not None and set_default_query is not None:
            raise ValueError("The `default_query` and `set_default_query` arguments are mutually exclusive")

        headers = self._custom_headers
        if default_headers is not None:
            headers = {**headers, **default_headers}
        elif set_default_headers is not None:
            headers = set_default_headers

        params = self._custom_query
        if default_query is not None:
            params = {**params, **default_query}
        elif set_default_query is not None:
            params = set_default_query

        http_client = http_client or self._client
        return self.__class__(
            username=username or self.username,
            password=password or self.password,
            base_url=base_url or self.base_url,
            timeout=self.timeout if isinstance(timeout, NotGiven) else timeout,
            http_client=http_client,
            max_retries=max_retries if is_given(max_retries) else self.max_retries,
            default_headers=headers,
            default_query=params,
            **_extra_kwargs,
        )

    # Alias for `copy` for nicer inline usage, e.g.
    # client.with_options(timeout=10).foo.create(...)
    with_options = copy

    @override
    def _make_status_error(
        self,
        err_msg: str,
        *,
        body: object,
        response: httpx.Response,
    ) -> APIStatusError:
        if response.status_code == 400:
            return _exceptions.BadRequestError(err_msg, response=response, body=body)

        if response.status_code == 401:
            return _exceptions.AuthenticationError(err_msg, response=response, body=body)

        if response.status_code == 403:
            return _exceptions.PermissionDeniedError(err_msg, response=response, body=body)

        if response.status_code == 404:
            return _exceptions.NotFoundError(err_msg, response=response, body=body)

        if response.status_code == 409:
            return _exceptions.ConflictError(err_msg, response=response, body=body)

        if response.status_code == 422:
            return _exceptions.UnprocessableEntityError(err_msg, response=response, body=body)

        if response.status_code == 429:
            return _exceptions.RateLimitError(err_msg, response=response, body=body)

        if response.status_code >= 500:
            return _exceptions.InternalServerError(err_msg, response=response, body=body)
        return APIStatusError(err_msg, response=response, body=body)


class AsyncWeaveTrace(AsyncAPIClient):
    # client options
    username: str
    password: str

    def __init__(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = not_given,
        max_retries: int = DEFAULT_MAX_RETRIES,
        default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        # Configure a custom httpx client.
        # We provide a `DefaultAsyncHttpxClient` class that you can pass to retain the default values we use for `limits`, `timeout` & `follow_redirects`.
        # See the [httpx documentation](https://www.python-httpx.org/api/#asyncclient) for more details.
        http_client: httpx.AsyncClient | None = None,
        # Enable or disable schema validation for data returned by the API.
        # When enabled an error APIResponseValidationError is raised
        # if the API responds with invalid data for the expected schema.
        #
        # This parameter may be removed or changed in the future.
        # If you rely on this feature, please open a GitHub issue
        # outlining your use-case to help us decide if it should be
        # part of our public interface in the future.
        _strict_response_validation: bool = False,
    ) -> None:
        """Construct a new async AsyncWeaveTrace client instance.

        This automatically infers the following arguments from their corresponding environment variables if they are not provided:
        - `username` from `WANDB_USERNAME`
        - `password` from `WANDB_API_KEY`
        """
        if username is None:
            username = os.environ.get("WANDB_USERNAME")
        if username is None:
            raise WeaveTraceError(
                "The username client option must be set either by passing username to the client or by setting the WANDB_USERNAME environment variable"
            )
        self.username = username

        if password is None:
            password = os.environ.get("WANDB_API_KEY")
        if password is None:
            raise WeaveTraceError(
                "The password client option must be set either by passing password to the client or by setting the WANDB_API_KEY environment variable"
            )
        self.password = password

        if base_url is None:
            base_url = os.environ.get("WEAVE_TRACE_BASE_URL")
        if base_url is None:
            base_url = f"https://trace.wandb.ai"

        custom_headers_env = os.environ.get("WEAVE_TRACE_CUSTOM_HEADERS")
        if custom_headers_env is not None:
            parsed: dict[str, str] = {}
            for line in custom_headers_env.split("\n"):
                colon = line.find(":")
                if colon >= 0:
                    parsed[line[:colon].strip()] = line[colon + 1 :].strip()
            default_headers = {**parsed, **(default_headers if is_mapping_t(default_headers) else {})}

        super().__init__(
            version=__version__,
            base_url=base_url,
            max_retries=max_retries,
            timeout=timeout,
            http_client=http_client,
            custom_headers=default_headers,
            custom_query=default_query,
            _strict_response_validation=_strict_response_validation,
        )

    @cached_property
    def services(self) -> AsyncServicesResource:
        from .resources.services import AsyncServicesResource

        return AsyncServicesResource(self)

    @cached_property
    def calls(self) -> AsyncCallsResource:
        from .resources.calls import AsyncCallsResource

        return AsyncCallsResource(self)

    @cached_property
    def objects(self) -> AsyncObjectsResource:
        from .resources.objects import AsyncObjectsResource

        return AsyncObjectsResource(self)

    @cached_property
    def tables(self) -> AsyncTablesResource:
        from .resources.tables import AsyncTablesResource

        return AsyncTablesResource(self)

    @cached_property
    def refs(self) -> AsyncRefsResource:
        from .resources.refs import AsyncRefsResource

        return AsyncRefsResource(self)

    @cached_property
    def files(self) -> AsyncFilesResource:
        from .resources.files import AsyncFilesResource

        return AsyncFilesResource(self)

    @cached_property
    def costs(self) -> AsyncCostsResource:
        from .resources.costs import AsyncCostsResource

        return AsyncCostsResource(self)

    @cached_property
    def feedback(self) -> AsyncFeedbackResource:
        from .resources.feedback import AsyncFeedbackResource

        return AsyncFeedbackResource(self)

    @cached_property
    def otel(self) -> AsyncOtelResource:
        from .resources.otel import AsyncOtelResource

        return AsyncOtelResource(self)

    @cached_property
    def trace(self) -> AsyncTraceResource:
        from .resources.trace import AsyncTraceResource

        return AsyncTraceResource(self)

    @cached_property
    def threads(self) -> AsyncThreadsResource:
        from .resources.threads import AsyncThreadsResource

        return AsyncThreadsResource(self)

    @cached_property
    def v2_ops(self) -> AsyncV2OpsResource:
        from .resources.v2_ops import AsyncV2OpsResource

        return AsyncV2OpsResource(self)

    @cached_property
    def v2_scorers(self) -> AsyncV2ScorersResource:
        from .resources.v2_scorers import AsyncV2ScorersResource

        return AsyncV2ScorersResource(self)

    @cached_property
    def v2_datasets(self) -> AsyncV2DatasetsResource:
        from .resources.v2_datasets import AsyncV2DatasetsResource

        return AsyncV2DatasetsResource(self)

    @cached_property
    def v2_evaluations(self) -> AsyncV2EvaluationsResource:
        from .resources.v2_evaluations import AsyncV2EvaluationsResource

        return AsyncV2EvaluationsResource(self)

    @cached_property
    def v2_models(self) -> AsyncV2ModelsResource:
        from .resources.v2_models import AsyncV2ModelsResource

        return AsyncV2ModelsResource(self)

    @cached_property
    def v2_evaluation_runs(self) -> AsyncV2EvaluationRunsResource:
        from .resources.v2_evaluation_runs import AsyncV2EvaluationRunsResource

        return AsyncV2EvaluationRunsResource(self)

    @cached_property
    def v2_predictions(self) -> AsyncV2PredictionsResource:
        from .resources.v2_predictions import AsyncV2PredictionsResource

        return AsyncV2PredictionsResource(self)

    @cached_property
    def v2_scores(self) -> AsyncV2ScoresResource:
        from .resources.v2_scores import AsyncV2ScoresResource

        return AsyncV2ScoresResource(self)

    @cached_property
    def with_raw_response(self) -> AsyncWeaveTraceWithRawResponse:
        return AsyncWeaveTraceWithRawResponse(self)

    @cached_property
    def with_streaming_response(self) -> AsyncWeaveTraceWithStreamedResponse:
        return AsyncWeaveTraceWithStreamedResponse(self)

    @property
    @override
    def qs(self) -> Querystring:
        return Querystring(array_format="comma")

    @property
    @override
    def auth_headers(self) -> dict[str, str]:
        credentials = f"{self.username}:{self.password}".encode("ascii")
        header = f"Basic {base64.b64encode(credentials).decode('ascii')}"
        return {"Authorization": header}

    @property
    @override
    def default_headers(self) -> dict[str, str | Omit]:
        return {
            **super().default_headers,
            "X-Stainless-Async": f"async:{get_async_library()}",
            **self._custom_headers,
        }

    def copy(
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        base_url: str | httpx.URL | None = None,
        timeout: float | Timeout | None | NotGiven = not_given,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int | NotGiven = not_given,
        default_headers: Mapping[str, str] | None = None,
        set_default_headers: Mapping[str, str] | None = None,
        default_query: Mapping[str, object] | None = None,
        set_default_query: Mapping[str, object] | None = None,
        _extra_kwargs: Mapping[str, Any] = {},
    ) -> Self:
        """
        Create a new client instance re-using the same options given to the current client with optional overriding.
        """
        if default_headers is not None and set_default_headers is not None:
            raise ValueError("The `default_headers` and `set_default_headers` arguments are mutually exclusive")

        if default_query is not None and set_default_query is not None:
            raise ValueError("The `default_query` and `set_default_query` arguments are mutually exclusive")

        headers = self._custom_headers
        if default_headers is not None:
            headers = {**headers, **default_headers}
        elif set_default_headers is not None:
            headers = set_default_headers

        params = self._custom_query
        if default_query is not None:
            params = {**params, **default_query}
        elif set_default_query is not None:
            params = set_default_query

        http_client = http_client or self._client
        return self.__class__(
            username=username or self.username,
            password=password or self.password,
            base_url=base_url or self.base_url,
            timeout=self.timeout if isinstance(timeout, NotGiven) else timeout,
            http_client=http_client,
            max_retries=max_retries if is_given(max_retries) else self.max_retries,
            default_headers=headers,
            default_query=params,
            **_extra_kwargs,
        )

    # Alias for `copy` for nicer inline usage, e.g.
    # client.with_options(timeout=10).foo.create(...)
    with_options = copy

    @override
    def _make_status_error(
        self,
        err_msg: str,
        *,
        body: object,
        response: httpx.Response,
    ) -> APIStatusError:
        if response.status_code == 400:
            return _exceptions.BadRequestError(err_msg, response=response, body=body)

        if response.status_code == 401:
            return _exceptions.AuthenticationError(err_msg, response=response, body=body)

        if response.status_code == 403:
            return _exceptions.PermissionDeniedError(err_msg, response=response, body=body)

        if response.status_code == 404:
            return _exceptions.NotFoundError(err_msg, response=response, body=body)

        if response.status_code == 409:
            return _exceptions.ConflictError(err_msg, response=response, body=body)

        if response.status_code == 422:
            return _exceptions.UnprocessableEntityError(err_msg, response=response, body=body)

        if response.status_code == 429:
            return _exceptions.RateLimitError(err_msg, response=response, body=body)

        if response.status_code >= 500:
            return _exceptions.InternalServerError(err_msg, response=response, body=body)
        return APIStatusError(err_msg, response=response, body=body)


class WeaveTraceWithRawResponse:
    _client: WeaveTrace

    def __init__(self, client: WeaveTrace) -> None:
        self._client = client

    @cached_property
    def services(self) -> services.ServicesResourceWithRawResponse:
        from .resources.services import ServicesResourceWithRawResponse

        return ServicesResourceWithRawResponse(self._client.services)

    @cached_property
    def calls(self) -> calls.CallsResourceWithRawResponse:
        from .resources.calls import CallsResourceWithRawResponse

        return CallsResourceWithRawResponse(self._client.calls)

    @cached_property
    def objects(self) -> objects.ObjectsResourceWithRawResponse:
        from .resources.objects import ObjectsResourceWithRawResponse

        return ObjectsResourceWithRawResponse(self._client.objects)

    @cached_property
    def tables(self) -> tables.TablesResourceWithRawResponse:
        from .resources.tables import TablesResourceWithRawResponse

        return TablesResourceWithRawResponse(self._client.tables)

    @cached_property
    def refs(self) -> refs.RefsResourceWithRawResponse:
        from .resources.refs import RefsResourceWithRawResponse

        return RefsResourceWithRawResponse(self._client.refs)

    @cached_property
    def files(self) -> files.FilesResourceWithRawResponse:
        from .resources.files import FilesResourceWithRawResponse

        return FilesResourceWithRawResponse(self._client.files)

    @cached_property
    def costs(self) -> costs.CostsResourceWithRawResponse:
        from .resources.costs import CostsResourceWithRawResponse

        return CostsResourceWithRawResponse(self._client.costs)

    @cached_property
    def feedback(self) -> feedback.FeedbackResourceWithRawResponse:
        from .resources.feedback import FeedbackResourceWithRawResponse

        return FeedbackResourceWithRawResponse(self._client.feedback)

    @cached_property
    def otel(self) -> otel.OtelResourceWithRawResponse:
        from .resources.otel import OtelResourceWithRawResponse

        return OtelResourceWithRawResponse(self._client.otel)

    @cached_property
    def trace(self) -> trace.TraceResourceWithRawResponse:
        from .resources.trace import TraceResourceWithRawResponse

        return TraceResourceWithRawResponse(self._client.trace)

    @cached_property
    def threads(self) -> threads.ThreadsResourceWithRawResponse:
        from .resources.threads import ThreadsResourceWithRawResponse

        return ThreadsResourceWithRawResponse(self._client.threads)

    @cached_property
    def v2_ops(self) -> v2_ops.V2OpsResourceWithRawResponse:
        from .resources.v2_ops import V2OpsResourceWithRawResponse

        return V2OpsResourceWithRawResponse(self._client.v2_ops)

    @cached_property
    def v2_scorers(self) -> v2_scorers.V2ScorersResourceWithRawResponse:
        from .resources.v2_scorers import V2ScorersResourceWithRawResponse

        return V2ScorersResourceWithRawResponse(self._client.v2_scorers)

    @cached_property
    def v2_datasets(self) -> v2_datasets.V2DatasetsResourceWithRawResponse:
        from .resources.v2_datasets import V2DatasetsResourceWithRawResponse

        return V2DatasetsResourceWithRawResponse(self._client.v2_datasets)

    @cached_property
    def v2_evaluations(self) -> v2_evaluations.V2EvaluationsResourceWithRawResponse:
        from .resources.v2_evaluations import V2EvaluationsResourceWithRawResponse

        return V2EvaluationsResourceWithRawResponse(self._client.v2_evaluations)

    @cached_property
    def v2_models(self) -> v2_models.V2ModelsResourceWithRawResponse:
        from .resources.v2_models import V2ModelsResourceWithRawResponse

        return V2ModelsResourceWithRawResponse(self._client.v2_models)

    @cached_property
    def v2_evaluation_runs(self) -> v2_evaluation_runs.V2EvaluationRunsResourceWithRawResponse:
        from .resources.v2_evaluation_runs import V2EvaluationRunsResourceWithRawResponse

        return V2EvaluationRunsResourceWithRawResponse(self._client.v2_evaluation_runs)

    @cached_property
    def v2_predictions(self) -> v2_predictions.V2PredictionsResourceWithRawResponse:
        from .resources.v2_predictions import V2PredictionsResourceWithRawResponse

        return V2PredictionsResourceWithRawResponse(self._client.v2_predictions)

    @cached_property
    def v2_scores(self) -> v2_scores.V2ScoresResourceWithRawResponse:
        from .resources.v2_scores import V2ScoresResourceWithRawResponse

        return V2ScoresResourceWithRawResponse(self._client.v2_scores)


class AsyncWeaveTraceWithRawResponse:
    _client: AsyncWeaveTrace

    def __init__(self, client: AsyncWeaveTrace) -> None:
        self._client = client

    @cached_property
    def services(self) -> services.AsyncServicesResourceWithRawResponse:
        from .resources.services import AsyncServicesResourceWithRawResponse

        return AsyncServicesResourceWithRawResponse(self._client.services)

    @cached_property
    def calls(self) -> calls.AsyncCallsResourceWithRawResponse:
        from .resources.calls import AsyncCallsResourceWithRawResponse

        return AsyncCallsResourceWithRawResponse(self._client.calls)

    @cached_property
    def objects(self) -> objects.AsyncObjectsResourceWithRawResponse:
        from .resources.objects import AsyncObjectsResourceWithRawResponse

        return AsyncObjectsResourceWithRawResponse(self._client.objects)

    @cached_property
    def tables(self) -> tables.AsyncTablesResourceWithRawResponse:
        from .resources.tables import AsyncTablesResourceWithRawResponse

        return AsyncTablesResourceWithRawResponse(self._client.tables)

    @cached_property
    def refs(self) -> refs.AsyncRefsResourceWithRawResponse:
        from .resources.refs import AsyncRefsResourceWithRawResponse

        return AsyncRefsResourceWithRawResponse(self._client.refs)

    @cached_property
    def files(self) -> files.AsyncFilesResourceWithRawResponse:
        from .resources.files import AsyncFilesResourceWithRawResponse

        return AsyncFilesResourceWithRawResponse(self._client.files)

    @cached_property
    def costs(self) -> costs.AsyncCostsResourceWithRawResponse:
        from .resources.costs import AsyncCostsResourceWithRawResponse

        return AsyncCostsResourceWithRawResponse(self._client.costs)

    @cached_property
    def feedback(self) -> feedback.AsyncFeedbackResourceWithRawResponse:
        from .resources.feedback import AsyncFeedbackResourceWithRawResponse

        return AsyncFeedbackResourceWithRawResponse(self._client.feedback)

    @cached_property
    def otel(self) -> otel.AsyncOtelResourceWithRawResponse:
        from .resources.otel import AsyncOtelResourceWithRawResponse

        return AsyncOtelResourceWithRawResponse(self._client.otel)

    @cached_property
    def trace(self) -> trace.AsyncTraceResourceWithRawResponse:
        from .resources.trace import AsyncTraceResourceWithRawResponse

        return AsyncTraceResourceWithRawResponse(self._client.trace)

    @cached_property
    def threads(self) -> threads.AsyncThreadsResourceWithRawResponse:
        from .resources.threads import AsyncThreadsResourceWithRawResponse

        return AsyncThreadsResourceWithRawResponse(self._client.threads)

    @cached_property
    def v2_ops(self) -> v2_ops.AsyncV2OpsResourceWithRawResponse:
        from .resources.v2_ops import AsyncV2OpsResourceWithRawResponse

        return AsyncV2OpsResourceWithRawResponse(self._client.v2_ops)

    @cached_property
    def v2_scorers(self) -> v2_scorers.AsyncV2ScorersResourceWithRawResponse:
        from .resources.v2_scorers import AsyncV2ScorersResourceWithRawResponse

        return AsyncV2ScorersResourceWithRawResponse(self._client.v2_scorers)

    @cached_property
    def v2_datasets(self) -> v2_datasets.AsyncV2DatasetsResourceWithRawResponse:
        from .resources.v2_datasets import AsyncV2DatasetsResourceWithRawResponse

        return AsyncV2DatasetsResourceWithRawResponse(self._client.v2_datasets)

    @cached_property
    def v2_evaluations(self) -> v2_evaluations.AsyncV2EvaluationsResourceWithRawResponse:
        from .resources.v2_evaluations import AsyncV2EvaluationsResourceWithRawResponse

        return AsyncV2EvaluationsResourceWithRawResponse(self._client.v2_evaluations)

    @cached_property
    def v2_models(self) -> v2_models.AsyncV2ModelsResourceWithRawResponse:
        from .resources.v2_models import AsyncV2ModelsResourceWithRawResponse

        return AsyncV2ModelsResourceWithRawResponse(self._client.v2_models)

    @cached_property
    def v2_evaluation_runs(self) -> v2_evaluation_runs.AsyncV2EvaluationRunsResourceWithRawResponse:
        from .resources.v2_evaluation_runs import AsyncV2EvaluationRunsResourceWithRawResponse

        return AsyncV2EvaluationRunsResourceWithRawResponse(self._client.v2_evaluation_runs)

    @cached_property
    def v2_predictions(self) -> v2_predictions.AsyncV2PredictionsResourceWithRawResponse:
        from .resources.v2_predictions import AsyncV2PredictionsResourceWithRawResponse

        return AsyncV2PredictionsResourceWithRawResponse(self._client.v2_predictions)

    @cached_property
    def v2_scores(self) -> v2_scores.AsyncV2ScoresResourceWithRawResponse:
        from .resources.v2_scores import AsyncV2ScoresResourceWithRawResponse

        return AsyncV2ScoresResourceWithRawResponse(self._client.v2_scores)


class WeaveTraceWithStreamedResponse:
    _client: WeaveTrace

    def __init__(self, client: WeaveTrace) -> None:
        self._client = client

    @cached_property
    def services(self) -> services.ServicesResourceWithStreamingResponse:
        from .resources.services import ServicesResourceWithStreamingResponse

        return ServicesResourceWithStreamingResponse(self._client.services)

    @cached_property
    def calls(self) -> calls.CallsResourceWithStreamingResponse:
        from .resources.calls import CallsResourceWithStreamingResponse

        return CallsResourceWithStreamingResponse(self._client.calls)

    @cached_property
    def objects(self) -> objects.ObjectsResourceWithStreamingResponse:
        from .resources.objects import ObjectsResourceWithStreamingResponse

        return ObjectsResourceWithStreamingResponse(self._client.objects)

    @cached_property
    def tables(self) -> tables.TablesResourceWithStreamingResponse:
        from .resources.tables import TablesResourceWithStreamingResponse

        return TablesResourceWithStreamingResponse(self._client.tables)

    @cached_property
    def refs(self) -> refs.RefsResourceWithStreamingResponse:
        from .resources.refs import RefsResourceWithStreamingResponse

        return RefsResourceWithStreamingResponse(self._client.refs)

    @cached_property
    def files(self) -> files.FilesResourceWithStreamingResponse:
        from .resources.files import FilesResourceWithStreamingResponse

        return FilesResourceWithStreamingResponse(self._client.files)

    @cached_property
    def costs(self) -> costs.CostsResourceWithStreamingResponse:
        from .resources.costs import CostsResourceWithStreamingResponse

        return CostsResourceWithStreamingResponse(self._client.costs)

    @cached_property
    def feedback(self) -> feedback.FeedbackResourceWithStreamingResponse:
        from .resources.feedback import FeedbackResourceWithStreamingResponse

        return FeedbackResourceWithStreamingResponse(self._client.feedback)

    @cached_property
    def otel(self) -> otel.OtelResourceWithStreamingResponse:
        from .resources.otel import OtelResourceWithStreamingResponse

        return OtelResourceWithStreamingResponse(self._client.otel)

    @cached_property
    def trace(self) -> trace.TraceResourceWithStreamingResponse:
        from .resources.trace import TraceResourceWithStreamingResponse

        return TraceResourceWithStreamingResponse(self._client.trace)

    @cached_property
    def threads(self) -> threads.ThreadsResourceWithStreamingResponse:
        from .resources.threads import ThreadsResourceWithStreamingResponse

        return ThreadsResourceWithStreamingResponse(self._client.threads)

    @cached_property
    def v2_ops(self) -> v2_ops.V2OpsResourceWithStreamingResponse:
        from .resources.v2_ops import V2OpsResourceWithStreamingResponse

        return V2OpsResourceWithStreamingResponse(self._client.v2_ops)

    @cached_property
    def v2_scorers(self) -> v2_scorers.V2ScorersResourceWithStreamingResponse:
        from .resources.v2_scorers import V2ScorersResourceWithStreamingResponse

        return V2ScorersResourceWithStreamingResponse(self._client.v2_scorers)

    @cached_property
    def v2_datasets(self) -> v2_datasets.V2DatasetsResourceWithStreamingResponse:
        from .resources.v2_datasets import V2DatasetsResourceWithStreamingResponse

        return V2DatasetsResourceWithStreamingResponse(self._client.v2_datasets)

    @cached_property
    def v2_evaluations(self) -> v2_evaluations.V2EvaluationsResourceWithStreamingResponse:
        from .resources.v2_evaluations import V2EvaluationsResourceWithStreamingResponse

        return V2EvaluationsResourceWithStreamingResponse(self._client.v2_evaluations)

    @cached_property
    def v2_models(self) -> v2_models.V2ModelsResourceWithStreamingResponse:
        from .resources.v2_models import V2ModelsResourceWithStreamingResponse

        return V2ModelsResourceWithStreamingResponse(self._client.v2_models)

    @cached_property
    def v2_evaluation_runs(self) -> v2_evaluation_runs.V2EvaluationRunsResourceWithStreamingResponse:
        from .resources.v2_evaluation_runs import V2EvaluationRunsResourceWithStreamingResponse

        return V2EvaluationRunsResourceWithStreamingResponse(self._client.v2_evaluation_runs)

    @cached_property
    def v2_predictions(self) -> v2_predictions.V2PredictionsResourceWithStreamingResponse:
        from .resources.v2_predictions import V2PredictionsResourceWithStreamingResponse

        return V2PredictionsResourceWithStreamingResponse(self._client.v2_predictions)

    @cached_property
    def v2_scores(self) -> v2_scores.V2ScoresResourceWithStreamingResponse:
        from .resources.v2_scores import V2ScoresResourceWithStreamingResponse

        return V2ScoresResourceWithStreamingResponse(self._client.v2_scores)


class AsyncWeaveTraceWithStreamedResponse:
    _client: AsyncWeaveTrace

    def __init__(self, client: AsyncWeaveTrace) -> None:
        self._client = client

    @cached_property
    def services(self) -> services.AsyncServicesResourceWithStreamingResponse:
        from .resources.services import AsyncServicesResourceWithStreamingResponse

        return AsyncServicesResourceWithStreamingResponse(self._client.services)

    @cached_property
    def calls(self) -> calls.AsyncCallsResourceWithStreamingResponse:
        from .resources.calls import AsyncCallsResourceWithStreamingResponse

        return AsyncCallsResourceWithStreamingResponse(self._client.calls)

    @cached_property
    def objects(self) -> objects.AsyncObjectsResourceWithStreamingResponse:
        from .resources.objects import AsyncObjectsResourceWithStreamingResponse

        return AsyncObjectsResourceWithStreamingResponse(self._client.objects)

    @cached_property
    def tables(self) -> tables.AsyncTablesResourceWithStreamingResponse:
        from .resources.tables import AsyncTablesResourceWithStreamingResponse

        return AsyncTablesResourceWithStreamingResponse(self._client.tables)

    @cached_property
    def refs(self) -> refs.AsyncRefsResourceWithStreamingResponse:
        from .resources.refs import AsyncRefsResourceWithStreamingResponse

        return AsyncRefsResourceWithStreamingResponse(self._client.refs)

    @cached_property
    def files(self) -> files.AsyncFilesResourceWithStreamingResponse:
        from .resources.files import AsyncFilesResourceWithStreamingResponse

        return AsyncFilesResourceWithStreamingResponse(self._client.files)

    @cached_property
    def costs(self) -> costs.AsyncCostsResourceWithStreamingResponse:
        from .resources.costs import AsyncCostsResourceWithStreamingResponse

        return AsyncCostsResourceWithStreamingResponse(self._client.costs)

    @cached_property
    def feedback(self) -> feedback.AsyncFeedbackResourceWithStreamingResponse:
        from .resources.feedback import AsyncFeedbackResourceWithStreamingResponse

        return AsyncFeedbackResourceWithStreamingResponse(self._client.feedback)

    @cached_property
    def otel(self) -> otel.AsyncOtelResourceWithStreamingResponse:
        from .resources.otel import AsyncOtelResourceWithStreamingResponse

        return AsyncOtelResourceWithStreamingResponse(self._client.otel)

    @cached_property
    def trace(self) -> trace.AsyncTraceResourceWithStreamingResponse:
        from .resources.trace import AsyncTraceResourceWithStreamingResponse

        return AsyncTraceResourceWithStreamingResponse(self._client.trace)

    @cached_property
    def threads(self) -> threads.AsyncThreadsResourceWithStreamingResponse:
        from .resources.threads import AsyncThreadsResourceWithStreamingResponse

        return AsyncThreadsResourceWithStreamingResponse(self._client.threads)

    @cached_property
    def v2_ops(self) -> v2_ops.AsyncV2OpsResourceWithStreamingResponse:
        from .resources.v2_ops import AsyncV2OpsResourceWithStreamingResponse

        return AsyncV2OpsResourceWithStreamingResponse(self._client.v2_ops)

    @cached_property
    def v2_scorers(self) -> v2_scorers.AsyncV2ScorersResourceWithStreamingResponse:
        from .resources.v2_scorers import AsyncV2ScorersResourceWithStreamingResponse

        return AsyncV2ScorersResourceWithStreamingResponse(self._client.v2_scorers)

    @cached_property
    def v2_datasets(self) -> v2_datasets.AsyncV2DatasetsResourceWithStreamingResponse:
        from .resources.v2_datasets import AsyncV2DatasetsResourceWithStreamingResponse

        return AsyncV2DatasetsResourceWithStreamingResponse(self._client.v2_datasets)

    @cached_property
    def v2_evaluations(self) -> v2_evaluations.AsyncV2EvaluationsResourceWithStreamingResponse:
        from .resources.v2_evaluations import AsyncV2EvaluationsResourceWithStreamingResponse

        return AsyncV2EvaluationsResourceWithStreamingResponse(self._client.v2_evaluations)

    @cached_property
    def v2_models(self) -> v2_models.AsyncV2ModelsResourceWithStreamingResponse:
        from .resources.v2_models import AsyncV2ModelsResourceWithStreamingResponse

        return AsyncV2ModelsResourceWithStreamingResponse(self._client.v2_models)

    @cached_property
    def v2_evaluation_runs(self) -> v2_evaluation_runs.AsyncV2EvaluationRunsResourceWithStreamingResponse:
        from .resources.v2_evaluation_runs import AsyncV2EvaluationRunsResourceWithStreamingResponse

        return AsyncV2EvaluationRunsResourceWithStreamingResponse(self._client.v2_evaluation_runs)

    @cached_property
    def v2_predictions(self) -> v2_predictions.AsyncV2PredictionsResourceWithStreamingResponse:
        from .resources.v2_predictions import AsyncV2PredictionsResourceWithStreamingResponse

        return AsyncV2PredictionsResourceWithStreamingResponse(self._client.v2_predictions)

    @cached_property
    def v2_scores(self) -> v2_scores.AsyncV2ScoresResourceWithStreamingResponse:
        from .resources.v2_scores import AsyncV2ScoresResourceWithStreamingResponse

        return AsyncV2ScoresResourceWithStreamingResponse(self._client.v2_scores)


Client = WeaveTrace

AsyncClient = AsyncWeaveTrace
