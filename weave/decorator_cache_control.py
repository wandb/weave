from .registry_mem import memory_registry
from .op_def import OpDef
from . import refs

import typing

_CACHE_CONTROLLERS: dict[
    OpDef, typing.Callable[[dict[str, refs.Ref], typing.Any], bool]
] = {}


def cache_control(op_uri: str):
    op = memory_registry.get_op(op_uri)

    def wrap(f: typing.Callable[[dict[str, refs.Ref], typing.Any], bool]):
        _CACHE_CONTROLLERS[op] = f

    return wrap


def get_cache_controller(op: OpDef):
    return _CACHE_CONTROLLERS.get(op, None)
