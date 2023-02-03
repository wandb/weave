# A thread that manages all Weave IO (we haven't migrated everything here yet).
# You can perform IO by using the get_sync_client or get_async_client interfaces.

# Warning: if you see errors coming from here, logging in the server process
# is not currently working. You can change logger.error to print to get stack
# traces in local development.
# TODO: Fix

import asyncio
import json
import socket
import dataclasses
import typing
import contextlib
import multiprocessing
import logging
import traceback
import threading
import queue
import atexit
import os

from . import wandb_client_api

from wandb.sdk.interface import artifacts


from . import artifact_wandb
from . import errors
from . import engine_trace
from . import filesystem
from . import weave_http
from . import wandb_api
from . import wandb_file_manager
from . import util


tracer = engine_trace.tracer()  # type: ignore

SOCKET_PATH = "/tmp/weave-io-service.sock"


class ArtifactMetadata(typing.TypedDict):
    created_at: str


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


@dataclasses.dataclass
class ServerRequest:
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


@dataclasses.dataclass
class ServerResponse:
    id: int
    value: typing.Any
    error: bool = False

    @classmethod
    def from_json(cls, json: typing.Any) -> "ServerResponse":
        return cls(**json)

    def to_json(self) -> typing.Any:
        return {"id": self.id, "value": self.value, "error": self.error}


class Server:
    def __init__(self, socket_path: str = SOCKET_PATH, process: bool = False) -> None:
        self.socket_path = socket_path + "-" + util.rand_string_n(10)
        self.ready_queue: typing.Union[queue.Queue, multiprocessing.Queue]
        self.process: typing.Union[threading.Thread, multiprocessing.Process]
        if process:
            self.ready_queue = multiprocessing.Queue()
            self.process = multiprocessing.Process(
                target=self.server_process, daemon=True
            )
        else:
            self.ready_queue = queue.Queue()
            self.process = threading.Thread(target=self.server_process, daemon=True)

    def start(self) -> None:
        self.process.start()
        self.ready_queue.get()

    def cleanup(self) -> None:
        try:
            os.remove(self.socket_path)
        except OSError:
            pass

    def server_process(self) -> None:
        asyncio.run(self.main(), debug=True)

    async def main(self) -> None:
        fs = filesystem.get_filesystem_async()
        net = weave_http.HttpAsync(fs)
        self.wandb_file_manager = wandb_file_manager.WandbFileManagerAsync(
            fs, net, await wandb_api.get_wandb_api()
        )
        server = await asyncio.start_unix_server(
            self.handle_connection, path=self.socket_path
        )
        atexit.register(self.cleanup)
        async with server:
            self.ready_queue.put(True)
            await server.serve_forever()

    async def handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        running_tasks = set()

        def _task_done(task: asyncio.Task) -> None:
            running_tasks.discard(task)
            e = task.exception()
            if e is not None:
                logging.error(
                    "WBArtifactManager crash: %s",
                    traceback.format_exception(e.__class__, e, e.__traceback__),
                )

        while True:
            req = await reader.readline()
            if not req:
                break
            task = asyncio.create_task(self.handle_raw(req, writer))
            running_tasks.add(task)
            task.add_done_callback(_task_done)

    async def handle_raw(
        self, req: typing.Optional[bytes], writer: asyncio.StreamWriter
    ) -> None:
        if not req:
            return
        decoded = req.decode()
        if not "\n" in decoded:
            # new newline means we got EOF
            return
        json_req = json.loads(decoded)
        server_req = ServerRequest.from_json(json_req)
        try:
            tracer.context_provider.activate(server_req.context.trace_context)
            with wandb_api.wandb_api_context(server_req.context.wandb_api_context):
                resp = await self.handle(server_req)
        except Exception as e:
            logging.error(
                "WBArtifactManager request error: %s\n", traceback.format_exc()
            )
            print("WBArtifactManager request error: %s\n", traceback.format_exc())
            error_response = ServerResponse(server_req.id, str(e), error=True)
            writer.write((json.dumps(error_response.to_json()) + "\n").encode())
            await writer.drain()
            return

        writer.write((json.dumps(resp.to_json()) + "\n").encode())
        await writer.drain()

    async def handle(self, req: ServerRequest) -> ServerResponse:
        with tracer.trace("WBArtifactManager.handle.%s" % req.name, service="weave-am"):
            handler = getattr(self, f"handle_{req.name}", None)
            if handler is None:
                raise errors.WeaveInternalError("No handler")
            resp = await handler(*req.args)
            return ServerResponse(req.id, resp)

    async def handle_ensure_manifest(self, artifact_uri: str) -> typing.Optional[str]:
        uri = artifact_wandb.WeaveWBArtifactURI.parse(artifact_uri)
        manifest_path = self.wandb_file_manager.manifest_path(uri)
        manifest = await self.wandb_file_manager.manifest(uri)
        if manifest is None:
            return None
        return manifest_path

    async def handle_ensure_file(self, artifact_uri: str) -> typing.Optional[str]:
        uri = artifact_wandb.WeaveWBArtifactURI.parse(artifact_uri)
        return await self.wandb_file_manager.ensure_file(uri)


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
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.request_id = 0
        self.requests: typing.Dict[int, asyncio.Future] = {}
        self.response_task = asyncio.create_task(self.handle_responses())
        self.response_task.add_done_callback(self.response_task_ended)

    def response_task_ended(self, task: asyncio.Task) -> None:
        exc = task.exception()
        if exc:
            print("IOServiceError", exc)
            traceback.print_exception(type(exc), exc, exc.__traceback__)
            raise exc

    async def close(self) -> None:
        self.writer.close()
        await self.writer.wait_closed()
        self.response_task.cancel()

    async def handle_responses(self) -> None:
        while True:
            resp = await self.reader.readline()
            if not resp:
                return
            decoded = resp.decode()
            if not "\n" in decoded:
                raise errors.WeaveWandbArtifactManagerError(
                    "Connection to ArtifactManager lost"
                )
            json_resp = json.loads(decoded)
            server_resp = ServerResponse.from_json(json_resp)
            self.requests[server_resp.id].set_result(server_resp)

    async def request(self, req: ServerRequest) -> ServerResponse:
        # Caller must check ServerResponse.error!
        req.id = self.request_id
        self.request_id += 1
        response_future: asyncio.Future[ServerResponse] = asyncio.Future()
        self.requests[req.id] = response_future
        self.writer.write((json.dumps(req.to_json()) + "\n").encode())
        await self.writer.drain()
        return await response_future


class AsyncClient:
    def __init__(self, server: Server) -> None:
        self.server = server

    @contextlib.asynccontextmanager
    async def connect(self) -> typing.AsyncGenerator[AsyncConnection, None]:
        self.reader, self.writer = await asyncio.open_unix_connection(
            self.server.socket_path
        )
        conn = AsyncConnection(self.reader, self.writer)
        try:
            yield conn
        finally:
            await conn.close()


class SyncClient:
    def __init__(self, server: Server, fs: filesystem.Filesystem) -> None:
        self.fs = fs
        self.server = server

    def request(self, name: str, *args: typing.Any) -> typing.Any:
        wb_ctx = wandb_api.get_wandb_api_context()
        cur_trace_context = tracer.current_trace_context()
        request = ServerRequest(
            name,
            args,
            ServerRequestContext(cur_trace_context, wb_ctx),
        )
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(self.server.socket_path)
            msg = (json.dumps(request.to_json()) + "\n").encode()
            sock.sendall(msg)
            resp_msgs = []
            # server uses writeline, so we read until \n
            while True:
                data = sock.recv(4096)
                if not data:
                    break
                resp_msgs.append(data)
                if ord("\n") in data:
                    break
        resp = b"".join(resp_msgs)

        decoded = resp.decode()
        if not "\n" in decoded:
            raise errors.WeaveWandbArtifactManagerError(
                "Connection to ArtifactManager lost"
            )
        json_resp = json.loads(decoded)
        server_resp = ServerResponse.from_json(json_resp)
        if server_resp.error:
            raise errors.WeaveWandbArtifactManagerError(
                "Request error: " + server_resp.value
            )
        return server_resp.value

    def manifest(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[artifacts.ArtifactManifest]:
        manifest_path: typing.Optional[str] = self.request(
            "ensure_manifest", str(artifact_uri)
        )
        if manifest_path is None:
            return None
        with self.fs.open_read(manifest_path) as f:
            return artifacts.ArtifactManifest.from_manifest_json(None, json.load(f))

    def ensure_file(
        self, artifact_uri: artifact_wandb.WeaveWBArtifactURI
    ) -> typing.Optional[str]:
        return self.request("ensure_file", str(artifact_uri))


def get_sync_client() -> SyncClient:
    return SyncClient(get_server(), filesystem.get_filesystem())
