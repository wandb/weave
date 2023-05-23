# Official interface for making http requests. All weave
# interactions with http servers should go through this interface.

import asyncio
import time
import os
import aiohttp
import types
import typing
import yarl
import logging
import requests


from . import engine_trace
from . import filesystem
from . import server_error_handling

logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
logging.getLogger("aiohttp.client").setLevel(logging.WARNING)
logging.getLogger("aiohttp.internal").setLevel(logging.WARNING)
logging.getLogger("aiohttp.server").setLevel(logging.WARNING)
logging.getLogger("aiohttp.web").setLevel(logging.WARNING)
logging.getLogger("aiohttp.websocket").setLevel(logging.WARNING)


tracer = engine_trace.tracer()  # type: ignore

# Turn on to print stats for each request
ENABLE_REQUEST_TRACING = False


def logging_trace_config() -> aiohttp.TraceConfig:
    def make_trace_event_handler(
        event_name: str,
    ) -> typing.Callable[
        [aiohttp.ClientSession, types.SimpleNamespace, typing.Any],
        typing.Coroutine[None, None, None],
    ]:
        async def on_event(
            session: aiohttp.ClientSession,
            trace_config_ctx: types.SimpleNamespace,
            params: typing.Any,
        ) -> None:
            if not hasattr(trace_config_ctx, "events"):
                trace_config_ctx.events = []
            trace_config_ctx.events.append(
                (event_name, asyncio.get_event_loop().time())
            )

        return on_event

    async def on_request_end(
        session: aiohttp.ClientSession,
        trace_config_ctx: types.SimpleNamespace,
        params: aiohttp.tracing.TraceRequestEndParams,
    ) -> None:
        trace_config_ctx.events.append(("redirect", asyncio.get_event_loop().time()))
        trace_config_ctx.events.append(("req_end", asyncio.get_event_loop().time()))
        events = trace_config_ctx.events
        prior_e = events[0]
        s = f"{prior_e[0]}"
        for e in events[1:]:
            s += f" [{e[1]-prior_e[1]:.3f}s] {e[0]}"
            prior_e = e
        print("Req done: ", time.time(), s)

    trace_config = aiohttp.TraceConfig()
    trace_config.on_connection_queued_start.append(
        make_trace_event_handler("queued_start")
    )
    trace_config.on_connection_queued_end.append(make_trace_event_handler("queued_end"))
    trace_config.on_connection_create_start.append(
        make_trace_event_handler("conn_create_start")
    )
    trace_config.on_connection_create_end.append(
        make_trace_event_handler("conn_create_end")
    )
    trace_config.on_request_start.append(make_trace_event_handler("request_start"))
    trace_config.on_request_start.append(make_trace_event_handler("request_redirect"))
    trace_config.on_request_end.append(on_request_end)
    return trace_config


class HttpAsync:
    def __init__(self, fs: filesystem.FilesystemAsync) -> None:
        self.fs = fs

        conn = aiohttp.TCPConnector(limit=50)
        trace_configs = []
        if ENABLE_REQUEST_TRACING:
            trace_configs.append(logging_trace_config())
        self.session = aiohttp.ClientSession(
            trace_configs=trace_configs,
            connector=conn,
            cookie_jar=aiohttp.DummyCookieJar(),
        )

    async def __aenter__(self) -> "HttpAsync":
        return self

    async def __aexit__(self, *args: typing.Any) -> None:
        await self.session.close()

    async def download_file(
        self,
        url: str,
        path: str,
        headers: typing.Optional[dict[str, str]] = None,
        cookies: typing.Optional[dict[str, str]] = None,
        auth: typing.Optional[aiohttp.BasicAuth] = None,
    ) -> None:
        await self.fs.makedirs(os.path.dirname(path), exist_ok=True)
        with tracer.trace("download_file_task"):
            # TODO: Error handling when no file or manifest

            # yarl.URL encoded=True is very important! Otherwise aiohttp
            # will encode the url again and we'll get a 404 for things like
            # signed URLs
            async with self.session.get(
                yarl.URL(url, encoded=True), headers=headers, cookies=cookies, auth=auth
            ) as r:
                if r.status == 200:
                    async with self.fs.open_write(path, mode="wb") as f:
                        async for data in r.content.iter_chunked(16 * 1024):
                            await f.write(data)
                else:
                    raise server_error_handling.WeaveInternalHttpException.from_code(
                        r.status, "Download failed"
                    )


class Http:
    def __init__(self, fs: filesystem.Filesystem) -> None:
        self.fs = fs
        self.session = requests.Session()

    def __enter__(self) -> "Http":
        return self

    def __exit__(self, *args: typing.Any) -> None:
        self.session.close()

    def download_file(
        self,
        url: str,
        path: str,
        headers: typing.Optional[dict[str, str]] = None,
        cookies: typing.Optional[dict[str, str]] = None,
    ) -> None:
        self.fs.makedirs(os.path.dirname(path), exist_ok=True)
        with tracer.trace("download_file_task"):
            # TODO: Error handling when no file or manifest

            # yarl.URL encoded=True is very important! Otherwise aiohttp
            # will encode the url again and we'll get a 404 for things like
            # signed URLs
            with self.session.get(
                str(yarl.URL(url, encoded=True)), headers=headers, cookies=cookies
            ) as r:
                if r.status_code == 200:  # type: ignore
                    with self.fs.open_write(path, mode="wb") as f:
                        f.write(r.content)  # type: ignore
                else:
                    raise server_error_handling.WeaveInternalHttpException.from_code(
                        r.status_code, "Download failed"  # type: ignore
                    )
