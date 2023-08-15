import contextvars
import contextlib
import typing
import dataclasses

from . import client_interface
from . import server_interface
from . import uris


# colab currently runs ipykernel < 6.0.  This resets context on every
# execution, see: https://github.com/ipython/ipykernel/pull/632.  We
# maintain a global context to work around this.
# NOTE: This logic assumes all ContextVars will exist as globals
# in this module with a leading underscore.
patch_context = False
try:
    import ipykernel
    from IPython.core.getipython import get_ipython

    if ipykernel.version_info[0] < 6:
        patch_context = True
except ImportError:
    pass

if patch_context:
    _context: typing.Dict[str, typing.Any] = dict()

    def weave_pre_run():
        glbs = globals()
        for k, v in _context.items():
            var = glbs.get("_" + k)
            if var is not None:
                var.set(v)

    def weave_post_run():
        _context.clear()
        for k, v in contextvars.copy_context().items():
            _context[k.name] = v

    ipython = get_ipython()
    if ipython is not None:
        # Incase this module is loaded multiple times
        for h in ipython.events.callbacks["pre_run_cell"]:
            if h.__name__ == "weave_pre_run":
                ipython.events.unregister("pre_run_cell", h)
        for h in ipython.events.callbacks["post_run_cell"]:
            if h.__name__ == "weave_post_run":
                ipython.events.unregister("post_run_cell", h)
        ipython.events.register("pre_run_cell", weave_pre_run)
        ipython.events.register("post_run_cell", weave_post_run)


# Set to the op uri if we're in the process of loading
# an op from an artifact.
_loading_op_location: contextvars.ContextVar[
    typing.Optional[uris.WeaveURI]
] = contextvars.ContextVar("loading_op_location", default=None)


# Set to true if we're in the process of loading builtin functions
# this prevents us from storing the op as an artifact
_loading_built_ins: contextvars.ContextVar[
    typing.Optional[bool]
] = contextvars.ContextVar("loading_built_ins", default=False)


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
    "eager_mode", default=False
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


_client_cache_key: contextvars.ContextVar[
    typing.Optional[str]
] = contextvars.ContextVar("client_cache_key", default=None)


@contextlib.contextmanager
def set_client_cache_key(key: typing.Optional[str] = None):
    token = _client_cache_key.set(key)
    try:
        yield
    finally:
        _client_cache_key.reset(token)


def get_client_cache_key():
    return _client_cache_key.get()


# Context for wandb api
# Instead of putting this in a shared file, we put it directly here
# so that the patching at the top of this file will work correctly
# for this symbol.
@dataclasses.dataclass
class WandbApiContext:
    user_id: typing.Optional[str] = None
    api_key: typing.Optional[str] = None
    headers: typing.Optional[dict[str, str]] = None
    cookies: typing.Optional[dict[str, str]] = None

    @classmethod
    def from_json(cls, json: typing.Any) -> "WandbApiContext":
        return cls(**json)

    def to_json(self) -> typing.Any:
        return dataclasses.asdict(self)


## wandb_api.py context
_wandb_api_context: contextvars.ContextVar[
    typing.Optional[WandbApiContext]
] = contextvars.ContextVar("wandb_api_context", default=None)
