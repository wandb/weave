import contextvars
import contextlib
import logging
import typing

from . import client
from . import server
from . import util


_weave_client: contextvars.ContextVar[
    typing.Optional[client.Client]
] = contextvars.ContextVar("weave_client", default=None)

_http_server: contextvars.ContextVar[
    typing.Optional[server.HttpServer]
] = contextvars.ContextVar("http_server", default=None)

_frontend_url: contextvars.ContextVar[typing.Optional[str]] = contextvars.ContextVar(
    "frontend_url", default=None
)


_analytics_enabled: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "analytics_enabled", default=True
)


@contextlib.contextmanager
def execution_client():
    """Returns a client for use by the execution engine and op resolvers."""
    # Force in process execution
    wc = client.Client(server.InProcessServer())
    client_token = _weave_client.set(wc)
    # Disable analytics
    analytics_token = _analytics_enabled.set(False)
    yield wc
    _weave_client.reset(client_token)
    _analytics_enabled.reset(analytics_token)


@contextlib.contextmanager
def local_http_client():
    s = server.HttpServer()
    s.start()
    server_token = _http_server.set(s)
    client_token = _weave_client.set(server.HttpServerClient(s.url))
    yield _weave_client.get()
    _weave_client.reset(client_token)
    _http_server.reset(server_token)


def _make_default_client():
    if util.is_notebook():
        serv = _http_server.get()
        if serv is None:
            serv = server.HttpServer()
            serv.start()
            _http_server.set(serv)

    # we are returning a client that does not talk to the http server we just created because
    # the http server only communicates with the frontend. we create it above so that there is
    # a running server for the frontend to talk to as soon as we call use() or show().
    # python code can use the in process server by default.
    return server.HttpServerClient("http://" + serv.host + ":" + str(serv.port))


def use_fixed_server_port():
    """Force Weave server to port 9994 so wandb frontend can talk to it."""
    s = server.HttpServer(port=9994)
    s.start()
    _weave_client.set(server.HttpServerClient(s.url))


def use_frontend_devmode():
    """Talk to external server running on 9994"""
    _weave_client.set(server.HttpServerClient("http://localhost:9994"))
    _frontend_url.set("https://app.wandb.test")


def use_frontend_url(url):
    _frontend_url.set(url)


def capture_weave_server_logs(log_level=logging.INFO):
    from . import weave_server

    weave_server.enable_stream_logging(log_level)


def get_client():
    c = _weave_client.get()
    if c is None:
        c = _make_default_client()
        _weave_client.set(c)
    return c


def get_frontend_url():
    url = _frontend_url.get()
    if url is None:
        client = get_client()
        if isinstance(client, server.HttpServerClient):
            url = client.url
        else:
            s = _http_server.get()
            if s is not None:
                url = s.url
            else:
                raise RuntimeError("Frontend server is not running")
    return url


def analytics_enabled():
    return _analytics_enabled.get()


def disable_analytics():
    return _analytics_enabled.set(False)
