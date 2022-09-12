from .registry_mem import memory_registry
from .decorator_op import get_signature
from .op_def import OpDef

from . import errors

import typing

_CACHE_CONTROLLERS: dict[OpDef, typing.Callable] = {}


def cache_control(op_uri: str):
    op = memory_registry.get_op(op_uri)
    op_sig = get_signature(op.resolve_fn)

    def wrap(f: typing.Callable):
        cache_control_sig = get_signature(f)
        if cache_control_sig.parameters != op_sig.parameters:
            raise errors.WeaveDefinitionError(
                "Cache control function parameters must match corresponding op resolver parameters"
            )
        _CACHE_CONTROLLERS[op] = f

    return wrap


def get_cache_controller(op: OpDef):
    return _CACHE_CONTROLLERS.get(op, None)
