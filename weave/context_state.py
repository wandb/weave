import contextvars
import contextlib
import typing

from . import client_interface
from . import server_interface
from . import uris


# Set to the op uri if we're in the process of loading
# an op from an artifact.
_loading_op_location: contextvars.ContextVar[
    typing.Optional[uris.WeaveURI]
] = contextvars.ContextVar("loading_op_location", default=None)


# Set to true if we're in the process of loading builtin functions
# this prevents us from storing the op as an artifact
_loading_built_ins: contextvars.ContextVar[
    typing.Optional[bool]
] = contextvars.ContextVar("loading_builtins", default=False)


@contextlib.contextmanager
def loading_op_location(location):
    token = _loading_op_location.set(location)
    yield _loading_op_location.get()
    _loading_op_location.reset(token)


def get_loading_op_location():
    return _loading_op_location.get()


def set_loading_built_ins() -> contextvars.Token:
    return _loading_built_ins.set(True)


def clear_loading_built_ins(token) -> None:
    _loading_built_ins.reset(token)


def get_loading_built_ins():
    return _loading_built_ins.get()


_analytics_enabled: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "analytics_enabled", default=True
)

_weave_client: contextvars.ContextVar[
    typing.Optional[client_interface.ClientInterface]
] = contextvars.ContextVar("weave_client", default=None)


@contextlib.contextmanager
def client(client: client_interface.ClientInterface):
    client_token = _weave_client.set(client)
    try:
        yield client
    finally:
        _weave_client.reset(client_token)


def get_client() -> typing.Optional[client_interface.ClientInterface]:
    return _weave_client.get()


def set_client(client: client_interface.ClientInterface):
    _weave_client.set(client)


_http_server: contextvars.ContextVar[
    typing.Optional[server_interface.BaseServer]
] = contextvars.ContextVar("http_server", default=None)


@contextlib.contextmanager
def server(server: server_interface.BaseServer):
    server_token = _http_server.set(server)
    try:
        yield server
    finally:
        _http_server.reset(server_token)


def get_server() -> typing.Optional[server_interface.BaseServer]:
    return _http_server.get()


def set_server(server: server_interface.BaseServer):
    _http_server.set(server)


_frontend_url: contextvars.ContextVar[typing.Optional[str]] = contextvars.ContextVar(
    "frontend_url", default=None
)


def get_frontend_url() -> typing.Optional[str]:
    return _frontend_url.get()


def set_frontend_url(url: str):
    _frontend_url.set(url)


_eager_mode: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_eager_mode", default=False
)


@contextlib.contextmanager
def eager_execution():
    eager_token = _eager_mode.set(True)
    try:
        yield
    finally:
        _eager_mode.reset(eager_token)


@contextlib.contextmanager
def lazy_execution():
    eager_token = _eager_mode.set(False)
    try:
        yield
    finally:
        _eager_mode.reset(eager_token)


def eager_mode():
    return _eager_mode.get()


@contextlib.contextmanager
def analytics_disabled():
    analytics_token = _analytics_enabled.set(False)
    try:
        yield
    finally:
        _analytics_enabled.reset(analytics_token)


def analytics_enabled():
    return _analytics_enabled.get()


def disable_analytics():
    return _analytics_enabled.set(False)
