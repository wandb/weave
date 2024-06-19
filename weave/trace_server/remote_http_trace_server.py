import io
import json
import logging
import sys
import typing as t

import requests
import tenacity
from pydantic import BaseModel, ValidationError

from weave.legacy.wandb_interface import project_creator
from weave.trace_server import environment as wf_env

from . import trace_server_interface as tsi
from .async_batch_processor import AsyncBatchProcessor

logger = logging.getLogger(__name__)


class StartBatchItem(BaseModel):
    mode: str = "start"
    req: tsi.CallStartReq


class EndBatchItem(BaseModel):
    mode: str = "end"
    req: tsi.CallEndReq


class Batch(BaseModel):
    batch: t.List[t.Union[StartBatchItem, EndBatchItem]]


class ServerInfoRes(BaseModel):
    min_required_weave_python_version: str


REMOTE_REQUEST_BYTES_LIMIT = (
    (32 - 1) * 1024 * 1024
)  # 32 MiB (real limit) - 1 MiB (buffer)

REMOTE_REQUEST_RETRY_DURATION = 60 * 60 * 36  # 36 hours
REMOTE_REQUEST_RETRY_MAX_INTERVAL = 60 * 5  # 5 minutes


def _is_retryable_exception(e: Exception) -> bool:
    # Don't retry pydantic validation errors
    if isinstance(e, ValidationError):
        return False

    # Don't retry on HTTP 4xx (except 429)
    if isinstance(e, requests.HTTPError) and e.response is not None:
        code_class = e.response.status_code // 100

        # Bad request, not rate-limiting
        if code_class == 4 and e.response.status_code != 429:
            return False

        # Unknown server error
        # TODO(np): We need to fix the server to return proper status codes
        # for downstream 401, 403, 404, etc... Those should propagate back to
        # the client.
        if e.response.status_code == 500:
            return False

    # Otherwise, retry: Non-500 5xx, OSError, ConnectionError, ConnectionResetError, IOError, etc...
    return True


def _log_retry(retry_state: tenacity.RetryCallState) -> None:
    logger.info(
        "retry_attempt",
        extra={
            "fn": retry_state.fn,
            "attempt_number": retry_state.attempt_number,
            "exception": str(retry_state.outcome.exception()),
        },
    )


def _log_failure(retry_state: tenacity.RetryCallState) -> t.Any:
    logger.info(
        "retry_failed",
        extra={
            "fn": retry_state.fn,
            "attempt_number": retry_state.attempt_number,
            "exception": str(retry_state.outcome.exception()),
        },
    )
    return retry_state.outcome.result()


class RemoteHTTPTraceServer(tsi.TraceServerInterface):
    trace_server_url: str

    # My current batching is not safe in notebooks, disable it for now
    def __init__(self, trace_server_url: str, should_batch: bool = False):
        super().__init__()
        self.trace_server_url = trace_server_url
        self.should_batch = should_batch
        if self.should_batch:
            self.call_processor = AsyncBatchProcessor(self._flush_calls)
        self._auth: t.Optional[t.Tuple[str, str]] = None

    def ensure_project_exists(self, entity: str, project: str) -> None:
        # TODO: This should happen in the wandb backend, not here, and it's slow
        # (hundreds of ms)
        project_creator.ensure_project_exists(entity, project)

    @classmethod
    def from_env(cls, should_batch: bool = False) -> "RemoteHTTPTraceServer":
        return cls(wf_env.wf_trace_server_url(), should_batch)

    def set_auth(self, auth: t.Tuple[str, str]) -> None:
        self._auth = auth

    @tenacity.retry(
        stop=tenacity.stop_after_delay(REMOTE_REQUEST_RETRY_DURATION),
        wait=tenacity.wait_exponential_jitter(
            initial=1, max=REMOTE_REQUEST_RETRY_MAX_INTERVAL
        ),
        retry=tenacity.retry_if_exception(_is_retryable_exception),
        before_sleep=_log_retry,
        retry_error_callback=_log_failure,
        reraise=True,
    )
    def _flush_calls(
        self,
        batch: t.List,
        *,
        _should_update_batch_size: bool = True,
    ) -> None:
        if len(batch) == 0:
            return

        data = Batch(batch=batch).model_dump_json()
        encoded_data = data.encode("utf-8")
        encoded_bytes = len(encoded_data)

        # Update target batch size (this allows us to have a dynamic batch size based on the size of the data being sent)
        estimated_bytes_per_item = encoded_bytes / len(batch)
        if _should_update_batch_size and estimated_bytes_per_item > 0:
            target_batch_size = int(
                REMOTE_REQUEST_BYTES_LIMIT // estimated_bytes_per_item
            )
            self.call_processor.max_batch_size = max(1, target_batch_size)

        # If the batch is too big, recursively split it in half
        if encoded_bytes > REMOTE_REQUEST_BYTES_LIMIT and len(batch) > 1:
            split_idx = int(len(batch) // 2)
            self._flush_calls(batch[:split_idx], _should_update_batch_size=False)
            self._flush_calls(batch[split_idx:], _should_update_batch_size=False)
            return

        r = requests.post(
            self.trace_server_url + "/call/upsert_batch",
            data=encoded_data,
            auth=self._auth,
        )
        r.raise_for_status()

    @tenacity.retry(
        stop=tenacity.stop_after_delay(REMOTE_REQUEST_RETRY_DURATION),
        wait=tenacity.wait_exponential_jitter(
            initial=1, max=REMOTE_REQUEST_RETRY_MAX_INTERVAL
        ),
        retry=tenacity.retry_if_exception(_is_retryable_exception),
        before_sleep=_log_retry,
        retry_error_callback=_log_failure,
        reraise=True,
    )
    def _generic_request_executor(
        self,
        url: str,
        req: BaseModel,
        stream: bool = False,
    ) -> requests.Response:
        r = requests.post(
            self.trace_server_url + url,
            # `by_alias` is required since we have Mongo-style properties in the
            # query models that are aliased to conform to start with `$`. Without
            # this, the model_dump will use the internal property names which are
            # not valid for the `model_validate` step.
            data=req.model_dump_json(by_alias=True).encode("utf-8"),
            auth=self._auth,
            stream=stream,
        )
        if r.status_code == 413 and "obj/create" in url:
            raise requests.HTTPError(
                "413 Client Error. Request too large. Try using a weave.Dataset() object."
            )
        if r.status_code == 500:
            reason_val = r.text
            try:
                reason_val = json.dumps(json.loads(reason_val), indent=2)
            except json.JSONDecodeError:
                reason_val = f"Reason: {reason_val}"
            raise requests.HTTPError(
                f"500 Server Error: Internal Server Error for url: {url}. {reason_val}",
                response=r,
            )
        r.raise_for_status()

        return r

    def _generic_request(
        self,
        url: str,
        req: BaseModel,
        req_model: t.Type[BaseModel],
        res_model: t.Type[BaseModel],
    ) -> BaseModel:
        if isinstance(req, dict):
            req = req_model.model_validate(req)
        r = self._generic_request_executor(url, req)
        return res_model.model_validate(r.json())

    def _generic_stream_request(
        self,
        url: str,
        req: BaseModel,
        req_model: t.Type[BaseModel],
        res_model: t.Type[BaseModel],
    ) -> t.Iterator[BaseModel]:
        if isinstance(req, dict):
            req = req_model.model_validate(req)
        r = self._generic_request_executor(url, req, stream=True)
        for line in r.iter_lines():
            if line:
                yield res_model.model_validate(json.loads(line))

    @tenacity.retry(
        stop=tenacity.stop_after_delay(REMOTE_REQUEST_RETRY_DURATION),
        wait=tenacity.wait_exponential_jitter(
            initial=1, max=REMOTE_REQUEST_RETRY_MAX_INTERVAL
        ),
        retry=tenacity.retry_if_exception(_is_retryable_exception),
        before_sleep=_log_retry,
        retry_error_callback=_log_failure,
        reraise=True,
    )
    def server_info(self) -> ServerInfoRes:
        r = requests.get(self.trace_server_url + "/server_info")
        r.raise_for_status()
        return ServerInfoRes.model_validate(r.json())

    # Call API
    def call_start(
        self, req: t.Union[tsi.CallStartReq, t.Dict[str, t.Any]]
    ) -> tsi.CallStartRes:
        if self.should_batch:
            req_as_obj: tsi.CallStartReq
            if isinstance(req, dict):
                req_as_obj = tsi.CallStartReq.model_validate(req)
            else:
                req_as_obj = req
            if req_as_obj.start.id == None or req_as_obj.start.trace_id == None:
                raise ValueError(
                    "CallStartReq must have id and trace_id when batching."
                )
            self.call_processor.enqueue([StartBatchItem(req=req_as_obj)])
            return tsi.CallStartRes(
                id=req_as_obj.start.id, trace_id=req_as_obj.start.trace_id
            )
        return self._generic_request(
            "/call/start", req, tsi.CallStartReq, tsi.CallStartRes
        )

    def call_end(
        self, req: t.Union[tsi.CallEndReq, t.Dict[str, t.Any]]
    ) -> tsi.CallEndRes:
        if self.should_batch:
            req_as_obj: tsi.CallEndReq
            if isinstance(req, dict):
                req_as_obj = tsi.CallEndReq.model_validate(req)
            else:
                req_as_obj = req
            self.call_processor.enqueue([EndBatchItem(req=req_as_obj)])
            return tsi.CallEndRes()
        return self._generic_request("/call/end", req, tsi.CallEndReq, tsi.CallEndRes)

    def call_read(
        self, req: t.Union[tsi.CallReadReq, t.Dict[str, t.Any]]
    ) -> tsi.CallReadRes:
        return self._generic_request(
            "/call/read", req, tsi.CallReadReq, tsi.CallReadRes
        )

    def calls_query(
        self, req: t.Union[tsi.CallsQueryReq, t.Dict[str, t.Any]]
    ) -> tsi.CallsQueryRes:
        return self._generic_request(
            "/calls/query", req, tsi.CallsQueryReq, tsi.CallsQueryRes
        )

    def calls_query_stream(self, req: tsi.CallsQueryReq) -> t.Iterator[tsi.CallSchema]:
        return self._generic_stream_request(
            "/calls/stream_query", req, tsi.CallsQueryReq, tsi.CallSchema
        )

    def calls_query_stats(
        self, req: t.Union[tsi.CallsQueryStatsReq, t.Dict[str, t.Any]]
    ) -> tsi.CallsQueryStatsRes:
        return self._generic_request(
            "/calls/query_stats", req, tsi.CallsQueryStatsReq, tsi.CallsQueryStatsRes
        )

    def calls_delete(
        self, req: t.Union[tsi.CallsDeleteReq, t.Dict[str, t.Any]]
    ) -> tsi.CallsDeleteRes:
        return self._generic_request(
            "/calls/delete", req, tsi.CallsDeleteReq, tsi.CallsDeleteRes
        )

    def call_update(
        self, req: t.Union[tsi.CallUpdateReq, t.Dict[str, t.Any]]
    ) -> tsi.CallUpdateRes:
        return self._generic_request(
            "/call/update", req, tsi.CallUpdateReq, tsi.CallUpdateRes
        )

    # Op API

    def op_create(
        self, req: t.Union[tsi.OpCreateReq, t.Dict[str, t.Any]]
    ) -> tsi.OpCreateRes:
        return self._generic_request(
            "/op/create", req, tsi.OpCreateReq, tsi.OpCreateRes
        )

    def op_read(self, req: t.Union[tsi.OpReadReq, t.Dict[str, t.Any]]) -> tsi.OpReadRes:
        return self._generic_request("/op/read", req, tsi.OpReadReq, tsi.OpReadRes)

    def ops_query(
        self, req: t.Union[tsi.OpQueryReq, t.Dict[str, t.Any]]
    ) -> tsi.OpQueryRes:
        return self._generic_request("/ops/query", req, tsi.OpQueryReq, tsi.OpQueryRes)

    # Obj API

    def obj_create(
        self, req: t.Union[tsi.ObjCreateReq, t.Dict[str, t.Any]]
    ) -> tsi.ObjCreateRes:
        return self._generic_request(
            "/obj/create", req, tsi.ObjCreateReq, tsi.ObjCreateRes
        )

    def obj_read(
        self, req: t.Union[tsi.ObjReadReq, t.Dict[str, t.Any]]
    ) -> tsi.ObjReadRes:
        return self._generic_request("/obj/read", req, tsi.ObjReadReq, tsi.ObjReadRes)

    def objs_query(
        self, req: t.Union[tsi.ObjQueryReq, t.Dict[str, t.Any]]
    ) -> tsi.ObjQueryRes:
        return self._generic_request(
            "/objs/query", req, tsi.ObjQueryReq, tsi.ObjQueryRes
        )

    def table_create(
        self, req: t.Union[tsi.TableCreateReq, t.Dict[str, t.Any]]
    ) -> tsi.TableCreateRes:
        return self._generic_request(
            "/table/create", req, tsi.TableCreateReq, tsi.TableCreateRes
        )

    def table_query(
        self, req: t.Union[tsi.TableQueryReq, t.Dict[str, t.Any]]
    ) -> tsi.TableQueryRes:
        return self._generic_request(
            "/table/query", req, tsi.TableQueryReq, tsi.TableQueryRes
        )

    def refs_read_batch(
        self, req: t.Union[tsi.RefsReadBatchReq, t.Dict[str, t.Any]]
    ) -> tsi.RefsReadBatchRes:
        return self._generic_request(
            "/refs/read_batch", req, tsi.RefsReadBatchReq, tsi.RefsReadBatchRes
        )

    @tenacity.retry(
        stop=tenacity.stop_after_delay(REMOTE_REQUEST_RETRY_DURATION),
        wait=tenacity.wait_exponential_jitter(
            initial=1, max=REMOTE_REQUEST_RETRY_MAX_INTERVAL
        ),
        retry=tenacity.retry_if_exception(_is_retryable_exception),
        before_sleep=_log_retry,
        retry_error_callback=_log_failure,
        reraise=True,
    )
    def file_create(self, req: tsi.FileCreateReq) -> tsi.FileCreateRes:
        r = requests.post(
            self.trace_server_url + "/files/create",
            auth=self._auth,
            data={"project_id": req.project_id},
            files={"file": (req.name, req.content)},
        )
        r.raise_for_status()
        return tsi.FileCreateRes.model_validate(r.json())

    @tenacity.retry(
        stop=tenacity.stop_after_delay(REMOTE_REQUEST_RETRY_DURATION),
        wait=tenacity.wait_exponential_jitter(
            initial=1, max=REMOTE_REQUEST_RETRY_MAX_INTERVAL
        ),
        retry=tenacity.retry_if_exception(_is_retryable_exception),
        before_sleep=_log_retry,
        retry_error_callback=_log_failure,
        reraise=True,
    )
    def file_content_read(self, req: tsi.FileContentReadReq) -> tsi.FileContentReadRes:
        r = requests.post(
            self.trace_server_url + "/files/content",
            json={"project_id": req.project_id, "digest": req.digest},
            auth=self._auth,
        )
        r.raise_for_status()
        # TODO: Should stream to disk rather than to memory
        bytes = io.BytesIO()
        bytes.writelines(r.iter_content())
        bytes.seek(0)
        return tsi.FileContentReadRes(content=bytes.read())

    def feedback_create(
        self, req: t.Union[tsi.FeedbackCreateReq, t.Dict[str, t.Any]]
    ) -> tsi.FeedbackCreateRes:
        return self._generic_request(
            "/feedback/create", req, tsi.FeedbackCreateReq, tsi.FeedbackCreateRes
        )

    def feedback_query(
        self, req: t.Union[tsi.FeedbackQueryReq, t.Dict[str, t.Any]]
    ) -> tsi.FeedbackQueryRes:
        return self._generic_request(
            "/feedback/query", req, tsi.FeedbackQueryReq, tsi.FeedbackQueryRes
        )

    def feedback_purge(
        self, req: t.Union[tsi.FeedbackPurgeReq, t.Dict[str, t.Any]]
    ) -> tsi.FeedbackPurgeRes:
        return self._generic_request(
            "/feedback/purge", req, tsi.FeedbackPurgeReq, tsi.FeedbackPurgeRes
        )
