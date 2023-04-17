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
import aioprocessing
import multiprocessing
import logging
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

from .queue import Queue, ThreadQueue, ProcessQueue
from typing import Any, Callable, Dict, TypeVar, Iterator


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


HandlerFunction = Callable[..., Any]


class HandlerNotFoundException(Exception):
    pass


async def make_404() -> typing.NoReturn:
    raise HandlerNotFoundException()


# Server class is responsible for managing server lifecycle and handling requests
class Server:
    def __init__(
        self,
        process: bool = False,
    ) -> None:
        self.handlers: Dict[str, HandlerFunction] = {}

        self.handler_process: typing.Union[threading.Thread, multiprocessing.Process]
        self.request_queue: Queue[ServerRequest]

        # The internal response queue is used to communicate results back between the server
        # process and the user process. The server process puts responses into this queue,
        # and then the Queue feeder thread puts them into the appropriate client response queue.
        self._internal_response_queue: Queue[ServerResponse]

        # just using a ThreadQueue here since this is for communication between two threads
        # that are both in the user process.
        self.client_response_queues: Dict[str, ThreadQueue[ServerResponse]] = {}

        self._server_process_ready = multiprocessing.Event()
        self._response_queue_feeder_thread_ready = threading.Event()
        self._shutting_down = multiprocessing.Event()

        # Register handlers
        self.register_handler("ensure_manifest", self.handle_ensure_manifest)
        self.register_handler("ensure_file", self.handle_ensure_file)
        self.register_handler("direct_url", self.handle_direct_url)
        self.register_handler("sleep", self.handle_sleep)

        if process:
            self.handler_process = aioprocessing.AioProcess(
                target=self.server_process, daemon=True, name="IO Server"
            )
            self.request_queue = ProcessQueue()
            self._internal_response_queue = ProcessQueue()
        else:
            self.handler_process = threading.Thread(
                target=self.server_process, daemon=True, name="IO Server"
            )
            self.request_queue = ThreadQueue()
            self._internal_response_queue = ThreadQueue()

        # runs in the user process and puts responses from the server into the appropriate
        # client-consumed response queues.
        self.response_queue_feeder_thread = threading.Thread(
            target=self.response_queue_feeder_process, daemon=True
        )

    # server_process runs the server's main coroutine
    def server_process(self) -> None:
        asyncio.run(self._server_main(), debug=True)

    # start starts the server thread or process
    def start(self) -> None:
        self.handler_process.start()
        self.response_queue_feeder_thread.start()
        self._server_process_ready.wait()
        self._response_queue_feeder_thread_ready.wait()
        atexit.register(self.shutdown)

    # cleanup performs cleanup actions, such as flushing stats
    def cleanup(self) -> None:
        statsd.flush()

    # shutdown stops the server and joins the thread/process
    def shutdown(self) -> None:
        self._shutting_down.set()

        if self.response_queue_feeder_thread.is_alive():
            self.response_queue_feeder_thread.join()

        if self.handler_process.is_alive():
            self.handler_process.join()

        self.cleanup()

    def response_queue_feeder_process(self) -> None:
        asyncio.run(self._response_queue_feeder_main(), debug=True)

    async def _response_queue_feeder_main(self) -> None:
        self._response_queue_feeder_thread_ready.set()
        while True:
            if self._shutting_down.is_set():
                break
            try:
                # TODO: investigate whether this would be better as a task
                resp = await self._internal_response_queue.async_get(block=False)
            except (queue.Empty, asyncio.queues.QueueEmpty, RuntimeError):
                await asyncio.sleep(1e-6)
                continue
            client_response_queue = self.client_response_queues[resp.client_id]
            # this is non-blocking b/c resp is already in memory
            client_response_queue.put(resp)

    # main is the server's main coroutine, handling incoming requests
    async def _server_main(self) -> None:

        # NOTHING SHOULD BLOCK IN THIS LOOP.
        # This loop runs in the non-user process.
        fs = filesystem.FilesystemAsync()
        net = weave_http.HttpAsync(fs)
        loop = asyncio.get_running_loop()
        active_tasks: set[asyncio.Task[typing.Any]] = set()
        async with net:
            self.wandb_file_manager = wandb_file_manager.WandbFileManagerAsync(
                fs, net, await wandb_api.get_wandb_api()
            )
            self._server_process_ready.set()
            while True:
                if self._shutting_down.is_set():
                    break
                try:
                    # dont block so that we dont hang shutdown
                    req = await self.request_queue.async_get(block=False)
                # TODO: do we need to catch this runtime error?
                except (queue.Empty, asyncio.queues.QueueEmpty, RuntimeError):
                    await asyncio.sleep(1e-6)
                    continue

                def make_task_done_callback(req: ServerRequest) -> Callable:
                    def task_done_callback(task: asyncio.Task) -> None:
                        exception = task.exception()
                        if exception:
                            if isinstance(exception, HandlerNotFoundException):
                                resp = req.error_response(404, exception)
                            else:
                                logging.error(
                                    "WBArtifactManager request error: %s\n",
                                    traceback.format_exc(),
                                )
                                print(
                                    "WBArtifactManager request error: %s\n",
                                    traceback.format_exc(),
                                )

                                resp = req.error_response(
                                    server_error_handling.maybe_extract_code_from_exception(
                                        exception  # type: ignore
                                    )
                                    or 500,
                                    exception,  # type: ignore
                                )
                        else:
                            resp = req.success_response(task.result())

                        active_tasks.discard(task)
                        new_task = loop.create_task(
                            self._internal_response_queue.async_put(resp)
                        )
                        active_tasks.add(new_task)
                        new_task.add_done_callback(active_tasks.discard)

                    return task_done_callback

                tracer.context_provider.activate(req.context.trace_context)
                with wandb_api.wandb_api_context(req.context.wandb_api_context):
                    if req.name not in self.handlers:
                        task = loop.create_task(make_404())
                    else:
                        # launch a task to handle the request
                        task = loop.create_task(self.handlers[req.name](*req.args))
                    active_tasks.add(task)
                    task_done_callback = make_task_done_callback(req)
                    task.add_done_callback(task_done_callback)
                self.request_queue.task_done()

    def register_handler(self, name: str, handler: HandlerFunction) -> None:
        self.handlers[name] = handler

    @contextlib.contextmanager
    def registered_client(
        self, client: typing.Union["AsyncClient", "SyncClient"]
    ) -> Iterator[None]:
        self.register_client(client.client_id)
        try:
            yield
        finally:
            self.unregister_client(client.client_id)

    def register_client(self, client_id: str) -> None:
        if client_id not in self.client_response_queues:
            self.client_response_queues[client_id] = ThreadQueue()

    def unregister_client(self, client_id: str) -> None:
        if client_id in self.client_response_queues:
            del self.client_response_queues[client_id]

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

    async def handle_sleep(self, seconds: float) -> float:
        # used for testing to simulate long running processes
        await asyncio.sleep(seconds)
        return seconds


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
        client_id: str,
        server: Server,
    ) -> None:

        self.client_id = client_id
        self.server = server
        response_queue = server.client_response_queues[client_id]
        request_queue = server.request_queue

        self.request_id = 0
        self.requests: typing.Dict[int, asyncio.Future] = {}
        self.request_queue: Queue[ServerRequest] = request_queue
        self.response_queue: Queue[ServerResponse] = response_queue
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
                resp = await self.response_queue.async_get(block=False)
            except queue.Empty:
                await asyncio.sleep(1e-6)
                continue
            self.response_queue.task_done()
            self.requests[resp.id].set_result(resp)

    async def request(self, name: str, *args: typing.Any) -> typing.Any:
        # Caller must check ServerResponse.error!
        wb_ctx = wandb_api.get_wandb_api_context()
        cur_trace_context = tracer.current_trace_context()

        req = ServerRequest(
            self.client_id,
            name,
            args,
            ServerRequestContext(cur_trace_context, wb_ctx),
            self.request_id,
        )

        self.request_id += 1
        response_future: asyncio.Future[ServerResponse] = asyncio.Future()
        self.requests[req.id] = response_future
        await self.request_queue.async_put(req)
        server_resp = await response_future

        if server_resp.error:
            if server_resp.http_error_code != None:
                raise server_error_handling.WeaveInternalHttpException.from_code(
                    server_resp.http_error_code
                )
            raise errors.WeaveWandbArtifactManagerError(
                "Request error: " + server_resp.value
            )

        return server_resp.value

    async def sleep(self, seconds: float) -> float:
        return await self.request("sleep", seconds)


class AsyncClient:
    def __init__(self, server: Server) -> None:
        self.client_id = str(uuid.uuid4())
        self.server = server

    @contextlib.asynccontextmanager
    async def connect(self) -> typing.AsyncGenerator[AsyncConnection, None]:
        with self.server.registered_client(self):
            conn = AsyncConnection(self.client_id, self.server)
            try:
                yield conn
            finally:
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

        with self.server.registered_client(self):
            request = ServerRequest(
                self.client_id,
                name,
                args,
                ServerRequestContext(cur_trace_context, wb_ctx),
                id=self._current_request_id,
            )

            response_queue = self.server.client_response_queues[self.client_id]
            self.server.request_queue.put(request)
            server_resp = response_queue.get()

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

    def sleep(self, seconds: float) -> None:
        self.request("sleep", seconds)


def get_sync_client() -> SyncClient:
    return SyncClient(get_server(), filesystem.get_filesystem())
