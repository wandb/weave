"""Snapshot mutable container structure so deferred work can't see post-call mutations.

The deferred `finish_call` path walks the call output on a worker thread
*after* the user's code has resumed. If the user mutates the output dict/list
in place, that mutation would otherwise reach into the deferred walk and
corrupt what gets saved. `snapshot_mutable_containers` rebuilds the spine of
plain `dict`/`list`/`set`/`tuple` containers up front so the walk is isolated.

Subclasses (`namedtuple`, `Counter`, `OrderedDict`, dict-subclass dataclasses)
and SDK leaf types (`Ref`, pydantic models, `ObjectRecord`, weave Objects) are
returned by identity. Rebuilding them as the bare type would strip information
the serializer needs; returning them by identity also preserves the contract
that `_save_nested_objects` mutates an Object to attach a ref the caller can
observe through their original handle.
"""

from __future__ import annotations

from typing import Any


def snapshot_mutable_containers(obj: Any, _memo: dict[int, Any] | None = None) -> Any:
    """Return a copy of `obj` with plain `dict`/`list`/`set`/`tuple` containers
    rebuilt at every level, so a caller mutating the original after
    `finish_call` returns cannot reach into the deferred output walk.

    Only EXACT `dict`/`list`/`set`/`tuple` are rebuilt. Subclasses
    (`namedtuple`, `Counter`, `OrderedDict`, dict-subclass dataclasses like
    `huggingface_hub.ChatCompletionOutput`) carry type information the
    serializer needs and are returned by identity. Rebuilding as the bare
    type would strip the subclass and silently change saved output shape
    (namedtuple field names lost, typed dict becomes plain dict, etc.).

    Frozensets, primitives, and SDK leaf types (Ref, pydantic BaseModel,
    ObjectRecord, weave Object/Table) are also returned by identity: they
    are either immutable or carry behavior we want preserved
    (e.g. `_save_nested_objects` mutating an Object to attach a ref).

    `_memo` maps `id(original) -> snapshot` so that aliased containers
    (the same list/dict appearing under multiple keys) get a single shared
    NEW copy across all aliases, and so that cycles terminate by returning
    the already-built snapshot on the second visit. Each mutable container
    is pre-registered in the memo BEFORE its children are walked, which is
    what makes cycles safe.
    """
    if _memo is None:
        _memo = {}
    cached = _memo.get(id(obj))
    if cached is not None:
        return cached
    t = type(obj)
    if t is dict:
        snap_d: dict = {}
        _memo[id(obj)] = snap_d
        for k, v in obj.items():
            snap_d[k] = snapshot_mutable_containers(v, _memo)
        return snap_d
    if t is list:
        snap_l: list = []
        _memo[id(obj)] = snap_l
        for v in obj:
            snap_l.append(snapshot_mutable_containers(v, _memo))
        return snap_l
    if t is set:
        snap_s: set = set()
        _memo[id(obj)] = snap_s
        for v in obj:
            snap_s.add(snapshot_mutable_containers(v, _memo))
        return snap_s
    if t is tuple:
        # Tuples are immutable, so a tuple can't be part of a cycle without
        # going through a mutable container first. We don't pre-register
        # the tuple result, but the memo still gives aliased mutables inside
        # the tuple a single shared snapshot.
        return tuple(snapshot_mutable_containers(v, _memo) for v in obj)
    return obj
