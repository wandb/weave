# A thread that manages all Weave IO (we haven't migrated everything here yet).
# You can perform IO by using the get_sync_client or get_async_client interfaces.

# Warning: if you see errors coming from here, logging in the server process
# is not currently working. You can change logger.error to print to get stack
# traces in local development.
# TODO: Fix

import time
import atexit
import queue
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
from . import async_queue
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


class ShutDown:
    def __eq__(self, other: Any) -> bool:
        return isinstance(other, ShutDown)


shutdown_request = ServerRequest("", "shutdown", (), ServerRequestContext(None, None))
shutdown_response = ServerResponse("", 0, ShutDown())

HandlerFunction = Callable[..., Any]


class HandlerNotFoundException(Exception):
    pass


# Server class is responsible for managing server lifecycle and handling requests
class Server:
    def __init__(
        self,
        process: bool = False,
    ) -> None:
        self.handlers: Dict[str, HandlerFunction] = {}

        self.request_handler: typing.Union[threading.Thread, aioprocessing.AioProcess]
        self.request_queue: async_queue.Queue[ServerRequest]

        # The internal response queue is used to communicate results back between the server
        # process and the user process. The server process puts responses into this queue,
        # and then the Queue feeder thread puts them into the appropriate client response queue.
        self._internal_response_queue: async_queue.Queue[ServerResponse]

        # just using a ThreadQueue here since this is for communication between two threads
        # that are both in the user process.
        self.client_response_queues: Dict[
            str,
            typing.Union[
                queue.Queue[ServerResponse], async_queue.ThreadQueue[ServerResponse]
            ],
        ] = {}

        self._shutting_down = multiprocessing.Event()
        self._shutdown_lock = multiprocessing.Lock()

        self._request_handler_ready_event = multiprocessing.Event()
        self._request_handler_ready_to_shut_down_event = multiprocessing.Event()

        self._response_queue_feeder_ready_event = threading.Event()
        self._response_queue_feeder_ready_to_shut_down_event = threading.Event()

        # Register handlers
        self.register_handler_fn("ensure_manifest", self.handle_ensure_manifest)
        self.register_handler_fn(
            "ensure_file_downloaded", self.handle_ensure_file_downloaded
        )
        self.register_handler_fn("ensure_file", self.handle_ensure_file)
        self.register_handler_fn("direct_url", self.handle_direct_url)
        self.register_handler_fn("sleep", self.handle_sleep)

        if process:
            self.request_handler = aioprocessing.AioProcess(
                target=self._request_handler_fn, name="IO Server", daemon=True
            )
            self.request_queue = async_queue.ProcessQueue()
            self._internal_response_queue = async_queue.ProcessQueue()
        else:
            self.request_handler = threading.Thread(
                target=self._request_handler_fn, name="IO Server", daemon=True
            )
            self.request_queue = async_queue.ThreadQueue()
            self._internal_response_queue = async_queue.ThreadQueue()

        # runs in the user process and puts responses from the server into the appropriate
        # client-consumed response queues.
        self.response_queue_router = threading.Thread(
            target=self._response_queue_router_fn, daemon=True
        )

    # server_process runs the server's main coroutine
    def _request_handler_fn(self) -> None:
        try:
            asyncio.run(self._request_handler_fn_main(), debug=True)
        except Exception as e:
            logging.exception(f"Error in request handler process: {e}")
            raise e

    # start starts the server thread or process
    def start(self) -> None:
        self.request_handler.start()
        self.response_queue_router.start()
        self._request_handler_ready_event.wait()
        self._response_queue_feeder_ready_event.wait()
        atexit.register(self.shutdown)

    # cleanup performs cleanup actions, such as flushing stats
    def cleanup(self) -> None:
        statsd.flush()

    # shutdown stops the server and joins the thread/process
    def shutdown(self) -> None:
        with self._shutdown_lock:
            self._shutting_down.set()

            # tell the two auxiliary processes to shutdown
            # (the server process and the response queue feeder thread)
            self.request_queue.put(shutdown_request)
            self._internal_response_queue.put(shutdown_response)

            self._response_queue_feeder_ready_to_shut_down_event.wait()
            self._request_handler_ready_to_shut_down_event.wait()

            self.response_queue_router.join()
            self.request_handler.join()
            self.cleanup()

    def _response_queue_router_fn(self) -> None:
        try:
            asyncio.run(self._response_queue_router_fn_main(), debug=True)
        except Exception as e:
            logging.exception(f"Error in response queue router: {e}")
            raise e

    async def _response_queue_router_fn_main(self) -> None:
        self._response_queue_feeder_ready_event.set()
        while True:
            try:
                resp = await self._internal_response_queue.async_get()
            except RuntimeError:
                # this happens when the interpreter is shutting down
                break
            if resp.value == ShutDown():
                self._internal_response_queue.task_done()
                self._internal_response_queue.join()
                break
            client_response_queue = self.client_response_queues[resp.client_id]
            # this is non-blocking b/c resp is already in memory
            client_response_queue.put(resp)
            self._internal_response_queue.task_done()
        # drain queue
        self._response_queue_feeder_ready_to_shut_down_event.set()

    async def _handle(self, req: ServerRequest) -> None:
        with tracer.trace("WBArtifactManager.handle.%s" % req.name, service="weave-am"):
            try:
                handler = self.handlers[req.name]
            except KeyError as e:
                resp = req.error_response(404, e)
            else:
                try:
                    val = await handler(*req.args)
                except Exception as e:
                    logging.error(
                        "WBArtifactManager request error: %s\n",
                        traceback.format_exc(),
                    )
                    print(
                        "WBArtifactManager request error: %s\n",
                        traceback.format_exc(),
                    )
                    resp = req.error_response(
                        server_error_handling.maybe_extract_code_from_exception(e)
                        or 500,
                        e,
                    )
                else:
                    resp = req.success_response(val)
            if isinstance(self._internal_response_queue, async_queue.ThreadQueue):
                # this is fast
                self._internal_response_queue.put(resp)
            else:
                # this needs to perform IPC
                await self._internal_response_queue.async_put(resp)

    # main is the server's main coroutine, handling incoming requests
    async def _request_handler_fn_main(self) -> None:
        # This loop should never block.
        fs = filesystem.FilesystemAsync()
        net = weave_http.HttpAsync(fs)
        loop = asyncio.get_running_loop()
        active_tasks: set[asyncio.Task[typing.Any]] = set()
        async with net:
            self.wandb_file_manager = wandb_file_manager.WandbFileManagerAsync(
                fs, net, await wandb_api.get_wandb_api()
            )

            self._request_handler_ready_event.set()
            while True:
                try:
                    req = await self.request_queue.async_get()
                except RuntimeError:
                    # this happens when the loop is shutting down
                    break
                if req.name == "shutdown":
                    self.request_queue.task_done()
                    self.request_queue.join()
                    break
                tracer.context_provider.activate(req.context.trace_context)
                with wandb_api.wandb_api_context(req.context.wandb_api_context):
                    # launch a task to handle the request
                    task = loop.create_task(self._handle(req))
                    active_tasks.add(task)
                    task.add_done_callback(active_tasks.discard)
                self.request_queue.task_done()
        self._request_handler_ready_to_shut_down_event.set()

    def register_handler_fn(self, name: str, handler: HandlerFunction) -> None:
        self.handlers[name] = handler

    @contextlib.contextmanager
    def registered_client(
        self, client: typing.Union["AsyncClient", "SyncClient"]
    ) -> Iterator[None]:
        self.register_client(client)
        try:
            yield
        finally:
            self.unregister_client(client)

    def register_client(
        self, client: typing.Union["SyncClient", "AsyncClient"]
    ) -> None:
        if client.client_id not in self.client_response_queues:
            if isinstance(client, SyncClient):
                self.client_response_queues[client.client_id] = queue.Queue()
            else:
                self.client_response_queues[
                    client.client_id
                ] = async_queue.ThreadQueue()

    def unregister_client(
        self, client: typing.Union["SyncClient", "AsyncClient"]
    ) -> None:
        if client.client_id in self.client_response_queues:
            del self.client_response_queues[client.client_id]

    async def handle_ensure_manifest(
        self, artifact_uri: str
    ) -> typing.Optional[artifact_wandb.WandbArtifactManifest]:
        uri = artifact_wandb.WeaveWBArtifactURI.parse(artifact_uri)
        return await self.wandb_file_manager.manifest(uri)

    async def handle_ensure_file(self, artifact_uri: str) -> typing.Optional[str]:
        uri = artifact_wandb.WeaveWBArtifactURI.parse(artifact_uri)
        return await self.wandb_file_manager.ensure_file(uri)

    async def handle_ensure_file_downloaded(
        self, download_url: str
    ) -> typing.Optional[str]:
        return await self.wandb_file_manager.ensure_file_downloaded(download_url)

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
        self.request_queue: async_queue.Queue[ServerRequest] = request_queue
        self.response_queue: async_queue.ThreadQueue[ServerResponse] = typing.cast(
            async_queue.ThreadQueue[ServerResponse], response_queue
        )
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
            resp = await self.response_queue.async_get()
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

        with self.server._shutdown_lock:
            is_shutting_down = self.server._shutting_down.is_set()

        if is_shutting_down:
            self.response_task.cancel()
            raise errors.WeaveWandbArtifactManagerError(
                "Server is shutting down, cannot make request"
            )

        if isinstance(self.request_queue, async_queue.ThreadQueue):
            # this is fast
            self.request_queue.put(req)
        else:
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

    async def manifest(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[artifact_wandb.WandbArtifactManifest]:
        manifest: typing.Optional[
            artifact_wandb.WandbArtifactManifest
        ] = await self.request("ensure_manifest", str(artifact_uri))
        return manifest

    async def ensure_file(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        res = await self.request("ensure_file", str(artifact_uri))
        return res

    async def ensure_file_downloaded(self, download_url: str) -> typing.Optional[str]:
        res = await self.request("ensure_file_downloaded", download_url)
        return res

    async def direct_url(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        res = await self.request("direct_url", str(artifact_uri))
        return res

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

            with self.server._shutdown_lock:
                is_shutting_down = self.server._shutting_down.is_set()

            if is_shutting_down:
                raise errors.WeaveWandbArtifactManagerError(
                    "Server is shutting down, cannot make request"
                )

            self.server.request_queue.put(request)
            server_resp = response_queue.get()
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

    def ensure_file_downloaded(self, download_url: str) -> typing.Optional[str]:
        return self.request("ensure_file_downloaded", download_url)

    def direct_url(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        return self.request("direct_url", str(artifact_uri))

    def sleep(self, seconds: float) -> None:
        return self.request("sleep", seconds)


class ServerlessClient:
    def __init__(self, fs: filesystem.Filesystem) -> None:
        self.fs = fs
        self.http = weave_http.Http(self.fs)
        self.wandb_api = wandb_api.WandbApi()
        self.wandb_file_manager = wandb_file_manager.WandbFileManager(
            self.fs, self.http, self.wandb_api
        )

    def manifest(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[artifact_wandb.WandbArtifactManifest]:
        return self.wandb_file_manager.manifest(artifact_uri)

    def ensure_file(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        return self.wandb_file_manager.ensure_file(artifact_uri)

    def ensure_file_downloaded(self, download_url: str) -> typing.Optional[str]:
        return self.wandb_file_manager.ensure_file_downloaded(download_url)

    def direct_url(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        return self.wandb_file_manager.direct_url(artifact_uri)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def get_sync_client() -> typing.Union[SyncClient, ServerlessClient]:
    # uncomment this for local debugging
    # return ServerlessClient(filesystem.get_filesystem())
    return SyncClient(get_server(), filesystem.get_filesystem())


def get_async_client() -> AsyncClient:
    return AsyncClient(get_server())
