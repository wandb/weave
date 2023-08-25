import contextlib
import logging
import os
import typing
from urllib.parse import urlparse

from weave.client_interface import ClientInterface

from . import util
from . import client
from . import server
from . import context_state


@contextlib.contextmanager
def execution_client():
    """Returns a client for use by the execution engine and op resolvers."""
    # Force in process execution
    with context_state.client(client.NonCachingClient(server.InProcessServer())):
        with context_state.analytics_disabled():
            yield


@contextlib.contextmanager
def local_http_client():
    s = server.HttpServer()
    s.start()
    with context_state.server(s):
        with context_state.client(server.HttpServerClient(s.url)):
            yield
    s.shutdown()


@contextlib.contextmanager
def weavejs_client():
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
    context_state.set_client(server.HttpServerClient("http://localhost:9994"))


def use_frontend_devmode():
    """Talk to external server running on 9994"""
    use_fixed_server_port()

    # point frontend to vite server
    context_state.set_frontend_url("http://localhost:3000")


def _make_default_client():
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
