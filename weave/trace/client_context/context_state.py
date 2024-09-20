import contextlib
import contextvars
import dataclasses
import typing

if typing.TYPE_CHECKING:
    from weave.trace.weave_client import WeaveClient


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

    def weave_pre_run() -> None:
        glbs = globals()
        for k, v in _context.items():
            var = glbs.get("_" + k)
            if var is not None:
                var.set(v)

    def weave_post_run() -> None:
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
_wandb_api_context: contextvars.ContextVar[typing.Optional[WandbApiContext]] = (
    contextvars.ContextVar("wandb_api_context", default=None)
)

## urls.py Context
_use_local_urls: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "use_local_urls", default=False
)

## graph_client_context.py Context
_graph_client: contextvars.ContextVar[typing.Optional["WeaveClient"]] = (
    contextvars.ContextVar("graph_client", default=None)
)


# Throw an error if op saving encounters an unknonwn condition.
# The default behavior is to warn.
_strict_op_saving: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "_strict_op_saving", default=False
)


def get_strict_op_saving() -> bool:
    return _strict_op_saving.get()


@contextlib.contextmanager
def strict_op_saving(enabled: bool) -> typing.Generator[bool, None, None]:
    token = _strict_op_saving.set(enabled)
    yield _strict_op_saving.get()
    _strict_op_saving.reset(token)
