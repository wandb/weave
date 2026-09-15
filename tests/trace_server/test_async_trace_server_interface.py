"""The async protocols must mirror the sync ones exactly."""

from __future__ import annotations

import inspect
import typing
from collections.abc import AsyncIterator, Iterator

from weave.trace_server import async_trace_server_interface as atsi
from weave.trace_server import trace_server_interface as tsi


def _methods(proto: type) -> dict[str, object]:
    return {
        name: member
        for name, member in vars(proto).items()
        if inspect.isfunction(member) and not name.startswith("_")
    }


def _expected_return(sync_fn: object) -> object:
    hints = typing.get_type_hints(sync_fn)
    ret = hints["return"]
    if typing.get_origin(ret) is Iterator:
        return AsyncIterator[typing.get_args(ret)]  # type: ignore[valid-type]
    return ret


def _check_pair(sync_proto: type, async_proto: type) -> None:
    sync_methods = _methods(sync_proto)
    async_methods = _methods(async_proto)
    assert sync_methods.keys() == async_methods.keys()
    for name, sync_fn in sync_methods.items():
        async_fn = async_methods[name]
        sync_hints = typing.get_type_hints(sync_fn)
        async_hints = typing.get_type_hints(async_fn)
        params = {k: v for k, v in sync_hints.items() if k != "return"}
        assert {k: v for k, v in async_hints.items() if k != "return"} == params, name
        assert inspect.signature(sync_fn).parameters.keys() == (
            inspect.signature(async_fn).parameters.keys()
        ), name
        expected = _expected_return(sync_fn)
        assert async_hints["return"] == expected, name
        if typing.get_origin(expected) is AsyncIterator:
            # An async generator is declared as a plain def returning AsyncIterator.
            assert not inspect.iscoroutinefunction(async_fn), name
        else:
            assert inspect.iscoroutinefunction(async_fn), name


def test_trace_server_interface_mirrors() -> None:
    _check_pair(tsi.TraceServerInterface, atsi.AsyncTraceServerInterface)


def test_object_interface_mirrors() -> None:
    _check_pair(tsi.ObjectInterface, atsi.AsyncObjectInterface)


def test_full_interface_composes_both() -> None:
    bases = atsi.AsyncFullTraceServerInterface.__mro__
    assert atsi.AsyncTraceServerInterface in bases
    assert atsi.AsyncObjectInterface in bases
