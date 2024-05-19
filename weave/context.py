import contextlib
import logging
import os
import typing
from urllib.parse import urlparse

from weave.client_interface import ClientInterface

from . import urls
from . import util
from . import client
from . import context_state


@contextlib.contextmanager
def execution_client():
    """Returns a client for use by the execution engine and op resolvers."""
    from . import server

    # Force in process execution
    with context_state.client(client.NonCachingClient(server.InProcessServer())):
        with context_state.analytics_disabled():
            yield


@contextlib.contextmanager
def local_http_client():
    from . import server

    s = server.HttpServer()
    s.start()
    with context_state.server(s):
        with context_state.client(server.HttpServerClient(s.url)):
            yield
    s.shutdown()


@contextlib.contextmanager
def weavejs_client():
    from . import server

    s = server.HttpServer()
    s.start()
    with context_state.server(s):
        with context_state.client(server.HttpServerClient(s.url, emulate_weavejs=True)):
            yield


def use_fixed_server_port():
    """Force Weave server to port 9994 so wandb frontend can talk to it."""
    # s = server.HttpServer(port=9994)
    # s.start()
    # _weave_client.set(server.HttpServerClient(s.url))
    from . import server

    context_state.set_client(server.HttpServerClient("http://localhost:9994"))


def use_frontend_devmode():
    """Talk to external server running on 9994"""
    use_fixed_server_port()
    urls.use_local_urls()

    # point frontend to vite server
    context_state.set_frontend_url("http://localhost:3000")


def use_lazy_execution():
    context_state._eager_mode.set(False)


lazy_execution = context_state.lazy_execution


def _make_default_client():
    from . import server

    if util.is_notebook():
        serv = context_state.get_server()
        if serv is None:
            frontend_url = os.environ.get("WEAVE_FRONTEND_URL")
            if frontend_url is not None:
                parsed_url = urlparse(frontend_url)
                server_args = {}
                if parsed_url.hostname is not None:
                    server_args["host"] = parsed_url.hostname
                if parsed_url.port is not None:
                    server_args["port"] = parsed_url.port
                serv = server.HttpServer(**server_args)
            else:
                serv = server.HttpServer()
            serv.start()
            context_state.set_server(serv)
        # Falling through here means the notebook kernel uses
        # InprocessServer, but the frontend uses HttpServer.
        # versions() doesn't work when we use the HttpServer currently.
        # return server.HttpServerClient(serv.url)

    return client.Client(server.InProcessServer())


def get_client() -> typing.Optional[ClientInterface]:
    c = context_state.get_client()
    if c is None:
        c = _make_default_client()
        context_state.set_client(c)
    return c


def get_frontend_url():
    from . import server

    url = os.environ.get("WEAVE_FRONTEND_URL", context_state.get_frontend_url())
    if url is None:
        client = get_client()
        if isinstance(client, server.HttpServerClient):
            url = client.url
        else:
            s = context_state.get_server()
            if s is not None:
                url = s.url
            else:
                raise RuntimeError("Frontend server is not running")
    url += "/__frontend/weave_jupyter"
    return url
