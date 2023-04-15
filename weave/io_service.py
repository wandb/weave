# A thread that manages all Weave IO (we haven't migrated everything here yet).
# You can perform IO by using the get_sync_client or get_async_client interfaces.

# Warning: if you see errors coming from here, logging in the server process
# is not currently working. You can change logger.error to print to get stack
# traces in local development.
# TODO: Fix

import queue
import atexit
import uuid
import asyncio
import dataclasses
import typing
import contextlib
import multiprocessing
import traceback
import threading


from . import artifact_wandb
from . import errors
from . import engine_trace
from . import filesystem
from . import weave_http
from . import wandb_api
from . import wandb_file_manager
from . import server_error_handling

from .async_queue import BaseAsyncQueue, AsyncThreadQueue, AsyncProcessQueue
from typing import Any, Callable, Dict, TypeVar


tracer = engine_trace.tracer()  # type: ignore
statsd = engine_trace.statsd()  # type: ignore


QueueItemType = TypeVar("QueueItemType")


class ArtifactMetadata(typing.TypedDict):
    created_at: str


# ServerRequestContext holds the context for server requests
@dataclasses.dataclass
class ServerRequestContext:
    trace_context: typing.Optional[engine_trace.TraceContext]
    wandb_api_context: typing.Optional[wandb_api.WandbApiContext]

    @classmethod
    def from_json(cls, json: typing.Any) -> "ServerRequestContext":
        trace_context = engine_trace.new_trace_context()
        if trace_context:
            trace_context.__setstate__(json["trace_context"])
        wandb_api_context = None
        wandb_api_context_json = json.get("wandb_api_context")
        if wandb_api_context_json:
            wandb_api_context = wandb_api.WandbApiContext.from_json(
                wandb_api_context_json
            )
        return cls(trace_context=trace_context, wandb_api_context=wandb_api_context)

    def to_json(self) -> typing.Any:
        trace_context = None
        if self.trace_context:
            trace_context = self.trace_context.__getstate__()
        wandb_ctx = None
        if self.wandb_api_context:
            wandb_ctx = self.wandb_api_context.to_json()
        return {
            "trace_context": trace_context,
            "wandb_api_context": wandb_ctx,
        }


# ServerRequest represents a request object sent to the server
@dataclasses.dataclass
class ServerRequest:
    client_id: str
    name: str
    args: typing.Tuple
    context: ServerRequestContext
    id: int = 0

    @classmethod
    def from_json(cls, json: typing.Any) -> "ServerRequest":
        json["context"] = ServerRequestContext.from_json(json["context"])
        return cls(**json)

    def to_json(self) -> typing.Any:
        return {
            "name": self.name,
            "args": self.args,
            "context": self.context.to_json(),
            "id": self.id,
        }

    def error_response(
        self, http_error_code: int, error: Exception
    ) -> "ServerResponse":
        return ServerResponse(
            http_error_code=http_error_code,
            client_id=self.client_id,
            id=self.id,
            # TODO(DG): this is a hack, we should be able to serialize the exception
            value=str(error),
            error=True,
        )

    def success_response(self, value: typing.Any) -> "ServerResponse":
        return ServerResponse(
            http_error_code=200,
            error=False,
            client_id=self.client_id,
            id=self.id,
            value=value,
        )


# ServerResponse represents a response object returned by the server
@dataclasses.dataclass
class ServerResponse:
    client_id: str
    id: int
    value: typing.Any
    error: bool = False
    http_error_code: typing.Optional[int] = None
    http_error_message: typing.Optional[str] = None

    @classmethod
    def from_json(cls, json: typing.Any) -> "ServerResponse":
        return cls(**json)

    def to_json(self) -> typing.Any:
        return {
            "id": self.id,
            "value": self.value,
            "error": self.error,
            "http_error_code": self.http_error_code,
        }


HandlerFunction = Callable[[], Any]


# Server class is responsible for managing server lifecycle and handling requests
class Server:
    def __init__(
        self,
        process: bool = False,
    ) -> None:
        self.handlers: Dict[str, HandlerFunction] = {}
        self.ready_queue: multiprocessing.Queue = multiprocessing.Queue()
        self.process: typing.Union[threading.Thread, multiprocessing.Process]
        self.request_queue: BaseAsyncQueue[ServerRequest]
        self.response_queues: Dict[str, BaseAsyncQueue[ServerResponse]] = {}
        self.response_queue_factory: Callable[[], BaseAsyncQueue[ServerResponse]]
        self.running = True
        self._shutdown_lock = threading.Lock()
        self._fs = filesystem.FilesystemAsync()
        self._net = weave_http.HttpAsync(self._fs)

        if process:
            self.request_queue = AsyncProcessQueue()
            self.response_queue_factory = AsyncProcessQueue
            self.process = multiprocessing.Process(
                target=self.server_process, daemon=True
            )
        else:
            self.request_queue = AsyncThreadQueue()
            self.response_queue_factory = AsyncThreadQueue
            self.process = threading.Thread(target=self.server_process, daemon=True)

    # server_process runs the server's main coroutine
    def server_process(self) -> None:
        asyncio.run(self.main(), debug=True)

    # start starts the server thread or process
    def start(self) -> None:
        self.process.start()
        self.ready_queue.get()

    # cleanup performs cleanup actions, such as flushing stats
    def cleanup(self) -> None:
        statsd.flush()

    # shutdown stops the server and joins the thread/process
    def shutdown(self) -> None:
        with self._shutdown_lock:
            self.running = False
            if self.process.is_alive():
                self.process.join()
            self.cleanup()
            asyncio.run(self._net.session.close())

    # main is the server's main coroutine, handling incoming requests
    async def main(self) -> None:

        self.wandb_file_manager = wandb_file_manager.WandbFileManagerAsync(
            self._fs, self._net, await wandb_api.get_wandb_api()
        )
        atexit.register(self.shutdown)
        self.ready_queue.put(True)
        while self.running:
            try:
                with self._shutdown_lock:
                    # dont block so that we dont hang shutdown
                    req = await self.request_queue.get(block=False)
            except (queue.Empty, RuntimeError):
                await asyncio.sleep(1e-6)  # wait 1 microsecond
                continue
            if req.name not in self.handlers:
                resp = req.error_response(
                    404, errors.WeaveBadRequest(f"No handler named {req.name!r}")
                )
            else:
                try:
                    resp = req.success_response(
                        await self.handlers[req.name](*req.args)
                    )
                except Exception as e:
                    resp = req.error_response(500, e)
            self.request_queue.task_done()
            await self.response_queues[req.client_id].put(resp)

    def register_handler(self, name: str, handler: HandlerFunction) -> None:
        self.handlers[name] = handler

    def register_client(self, client_id: str) -> None:
        if client_id not in self.response_queues:
            self.response_queues[client_id] = self.response_queue_factory()

    def unregister_client(self, client_id: str) -> None:
        if client_id in self.response_queues:
            del self.response_queues[client_id]

    async def handle_ensure_manifest(
        self, artifact_uri: str
    ) -> typing.Optional[artifact_wandb.WandbArtifactManifest]:
        uri = artifact_wandb.WeaveWBArtifactURI.parse(artifact_uri)
        return await self.wandb_file_manager.manifest(uri)

    async def handle_ensure_file(self, artifact_uri: str) -> typing.Optional[str]:
        uri = artifact_wandb.WeaveWBArtifactURI.parse(artifact_uri)
        return await self.wandb_file_manager.ensure_file(uri)

    async def handle_direct_url(self, artifact_uri: str) -> typing.Optional[str]:
        uri = artifact_wandb.WeaveWBArtifactURI.parse(artifact_uri)
        return await self.wandb_file_manager.direct_url(uri)


SERVER = None
SERVER_START_LOCK = threading.Lock()


def get_server() -> Server:
    global SERVER
    with SERVER_START_LOCK:
        if SERVER is None:
            SERVER = Server(process=False)
            SERVER.start()
        return SERVER


class AsyncConnection:
    def __init__(
        self,
        request_queue: BaseAsyncQueue[ServerRequest],
        response_queue: BaseAsyncQueue[ServerResponse],
    ) -> None:
        self.request_id = 0
        self.requests: typing.Dict[int, asyncio.Future] = {}
        self.request_queue: BaseAsyncQueue[ServerRequest] = request_queue
        self.response_queue: BaseAsyncQueue[ServerResponse] = response_queue
        self.response_task = asyncio.create_task(self.handle_responses())
        self.response_task.add_done_callback(self.response_task_ended)
        self.connected = True

    def response_task_ended(self, task: asyncio.Task) -> None:
        exc = task.exception()
        if exc:
            print("IOServiceError", exc)
            traceback.print_exception(type(exc), exc, exc.__traceback__)
            raise exc

    async def close(self) -> None:
        self.connected = False

    async def handle_responses(self) -> None:
        while self.connected:
            try:
                resp = await self.response_queue.get(block=False)
            except queue.Empty:
                await asyncio.sleep(1e-6)
                continue
            self.requests[resp.id].set_result(resp)

    async def request(self, req: ServerRequest) -> ServerResponse:
        # Caller must check ServerResponse.error!
        req.id = self.request_id
        self.request_id += 1
        response_future: asyncio.Future[ServerResponse] = asyncio.Future()
        self.requests[req.id] = response_future
        await self.request_queue.put(req)
        return await response_future


class AsyncClient:
    def __init__(self, server: Server) -> None:
        self.client_id = str(uuid.uuid4())
        self.server = server

    @contextlib.asynccontextmanager
    async def connect(self) -> typing.AsyncGenerator[AsyncConnection, None]:
        self.server.register_client(self.client_id)
        conn = AsyncConnection(
            self.server.request_queue, self.server.response_queues[self.client_id]
        )
        try:
            yield conn
        finally:
            self.server.unregister_client(self.client_id)
            await conn.close()


class SyncClient:
    def __init__(self, server: Server, fs: filesystem.Filesystem) -> None:
        self.client_id = str(uuid.uuid4())
        self.fs = fs
        self.server = server
        self._current_request_id = 0

    def request(self, name: str, *args: typing.Any) -> typing.Any:
        wb_ctx = wandb_api.get_wandb_api_context()
        cur_trace_context = tracer.current_trace_context()
        self._current_request_id += 1

        request = ServerRequest(
            self.client_id,
            name,
            args,
            ServerRequestContext(cur_trace_context, wb_ctx),
            id=self._current_request_id,
        )

        response_queue = self.server.response_queues[self.client_id]

        # loop = asyncio.get_event_loop()
        asyncio.run(self.server.request_queue.put(request))
        server_resp = asyncio.run(response_queue.get())
        response_queue.task_done()

        if server_resp.error:
            if server_resp.http_error_code != None:
                raise server_error_handling.WeaveInternalHttpException.from_code(
                    server_resp.http_error_code
                )
            raise errors.WeaveWandbArtifactManagerError(
                "Request error: " + server_resp.value
            )
        return server_resp.value

    def manifest(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[artifact_wandb.WandbArtifactManifest]:
        manifest: typing.Optional[artifact_wandb.WandbArtifactManifest] = self.request(
            "ensure_manifest", str(artifact_uri)
        )
        return manifest

    def ensure_file(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        return self.request("ensure_file", str(artifact_uri))

    def direct_url(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        return self.request("direct_url", str(artifact_uri))


def get_sync_client() -> SyncClient:
    return SyncClient(get_server(), filesystem.get_filesystem())
