"""Helpers for converting trace refs with copy-on-write traversal.

Trace request payloads pass through this module on every call_start /
call_end so external `weave:///...` refs can be rewritten to internal
`weave-trace-internal:///...` form (and vice versa). The naive recursion
that used to live here cloned every container on every request, which
dominated the hot path under load even when no refs were present.

The traversal here is copy-on-write: subtrees that contain no rewrites
return the original object, and a parent only allocates a new container
once one of its children has actually changed. For ref-free payloads
zero new objects are allocated.

Pydantic models with nested dataclasses inside `Any` fields fall back to
the legacy `model_dump` / `model_validate` round-trip, since Pydantic
does not round-trip dataclasses safely through getattr / setattr.

Refs can also be buried inside a JSON-serialized string leaf (e.g. an agent
message's `content` parts array). Such leaves are decoded and re-walked so the
embedded refs convert with the same semantics as top-level ones, bounded by
`_MAX_REF_SEARCH_DEPTH` to cap JSON-in-JSON nesting.
"""

import dataclasses
import json
import logging
from collections.abc import Callable
from typing import Any, NamedTuple, TypeVar, cast

from pydantic import BaseModel

from weave.shared import refs_internal as ri
from weave.trace_server.errors import InvalidExternalRef

logger = logging.getLogger(__name__)

A = TypeVar("A")
B = TypeVar("B")

weave_prefix = ri.WEAVE_SCHEME + ":///"
weave_internal_prefix = ri.WEAVE_INTERNAL_SCHEME + ":///"

# Caps the JSON-in-JSON descent for refs embedded inside a JSON-serialized
# string leaf: a decoded blob can hold another JSON-string leaf, so a
# pathological payload could nest without bound. Realistic nesting is a few
# levels; 8 leaves headroom below sys.getrecursionlimit(). Mirrors
# ``chat_view._MAX_REF_SEARCH_DEPTH``.
_MAX_REF_SEARCH_DEPTH = 8


class InvalidInternalRef(ValueError):
    pass


def _convert_embedded_json_refs(s: str, mapper: Callable[[Any], Any]) -> str:
    """Rewrite refs buried inside a JSON-serialized string ``s``.

    Decode ``s`` as JSON and re-run ``mapper`` over the result so embedded refs
    convert with the same semantics as top-level leaves. Returns ``s`` unchanged
    when it does not parse as JSON or when nothing inside it changed (avoiding a
    gratuitous re-dump); otherwise returns the re-serialized structure. Any
    exception from ``mapper`` propagates, preserving whole-string raise
    semantics.
    """
    try:
        parsed = json.loads(s)
    except (ValueError, TypeError):
        return s
    result = _map_values(parsed, mapper)
    if result is parsed:
        return s
    return json.dumps(result)


def _make_ref_string_mapper(
    convert_ref: Callable[[str, bool], str],
) -> Callable[[B], B]:
    """Build a copy-on-write mapper that rewrites weave refs in string leaves.

    ``convert_ref`` handles a string that starts with a ref prefix (plus a bool
    marking whether the leaf sits inside an embedded JSON blob), returning its
    converted form (or raising for a disallowed ref). A string that instead
    embeds a ref inside a JSON blob (e.g. a message ``content`` parts array) is
    decoded and re-run through the same mapper so embedded refs convert like
    top-level ones. The substring pre-check keeps ref-free strings off the
    ``json.loads`` path, and ``_MAX_REF_SEARCH_DEPTH`` caps the JSON-in-JSON
    descent.
    """
    depth = 0

    def mapper(obj: B) -> B:
        nonlocal depth
        if not isinstance(obj, str):
            return obj
        if obj.startswith(weave_prefix) or obj.startswith(weave_internal_prefix):
            return cast(B, convert_ref(obj, depth > 0))
        if depth < _MAX_REF_SEARCH_DEPTH and (
            weave_prefix in obj or weave_internal_prefix in obj
        ):
            depth += 1
            try:
                return cast(B, _convert_embedded_json_refs(obj, mapper))
            finally:
                depth -= 1
        return obj

    return mapper


def replace_external_weave_ref(
    ref_str: str,
    convert_ext_to_int_project_id: Callable[[str], str],
    cache: dict[str, str] | None = None,
) -> str:
    """Convert a single `weave:///entity/project/tail` ref to internal form.

    Pass a shared `cache` dict to amortize ext→int project lookups across
    repeated calls. Raises ``ValueError`` if the input does not start with
    the external scheme prefix, and ``InvalidExternalRef`` if the tail does
    not parse as ``entity/project/...``.
    """
    if not ref_str.startswith(weave_prefix):
        raise ValueError(f"Invalid URI: {ref_str}")
    rest = ref_str[len(weave_prefix) :]
    parts = rest.split("/", 2)
    if len(parts) != 3:
        raise InvalidExternalRef(f"Invalid URI: {ref_str}")
    entity, project, tail = parts
    project_key = f"{entity}/{project}"
    if cache is None:
        internal_project_id = convert_ext_to_int_project_id(project_key)
    else:
        if project_key not in cache:
            cache[project_key] = convert_ext_to_int_project_id(project_key)
        internal_project_id = cache[project_key]
    return f"{ri.WEAVE_INTERNAL_SCHEME}:///{internal_project_id}/{tail}"


def universal_ext_to_int_ref_converter(
    obj: A,
    convert_ext_to_int_project_id: Callable[[str], str],
    verify_internal_project_id: Callable[[str], bool] | None = None,
) -> A:
    """Takes any object and recursively replaces all external references with
    internal references. The external references are expected to be in the
    format of `weave:///entity/project/...` and the internal references are
    expected to be in the format of `weave-trace-internal:///project_id/...`.

    Args:
        obj: The object to convert.
        convert_ext_to_int_project_id: A function that takes an external
            project ID and returns the internal project ID.
        verify_internal_project_id: Optional callback that returns True if
            the given internal project_id should be accepted. Callers
            typically build this to accept the request's own project_id
            (fast set check) and fall back to an access check for
            cross-project refs.

    Returns:
        The object with all external references replaced with internal
        references.
    """
    ext_to_int_project_cache: dict[str, str] = {}

    def convert_ref(ref_str: str, embedded: bool) -> str:
        if ref_str.startswith(weave_prefix):
            return replace_external_weave_ref(
                ref_str, convert_ext_to_int_project_id, ext_to_int_project_cache
            )
        # Internal ref: accept only when the verify callback confirms the
        # project_id, else a client could smuggle refs to arbitrary private
        # projects.
        rest = ref_str[len(weave_internal_prefix) :]
        parts = rest.split("/", 2)
        if len(parts) < 2:
            raise InvalidExternalRef(
                "Invalid internal ref format: missing project_id or kind."
            )
        if verify_internal_project_id is not None and verify_internal_project_id(
            parts[0]
        ):
            return ref_str
        raise InvalidExternalRef("Encountered unexpected internal ref format.")

    return _map_values(obj, _make_ref_string_mapper(convert_ref))


C = TypeVar("C")


def universal_int_to_ext_ref_converter(
    obj: C,
    convert_int_to_ext_project_id: Callable[[str], str | None],
    tolerate_external_refs: bool = False,
) -> C:
    """Takes any object and recursively replaces all internal references with
    external references. The internal references are expected to be in the
    format of `weave-trace-internal:///project_id/...` and the external references are
    expected to be in the format of `weave:///entity/project/...`.

    Args:
        obj: The object to convert.
        convert_int_to_ext_project_id: A function that takes an internal
            project ID and returns the external project ID.
        tolerate_external_refs: When True, a top-level ref already in
            external (`weave:///`) form is logged and passed through instead
            of raising. Used by agent reads, whose ingest path does not fully
            convert refs and can therefore persist external refs. External
            refs embedded in JSON-string leaves are always passed through:
            rows written before the converter descended into JSON strings
            legitimately contain them.

    Returns:
        The object with all internal references replaced with external
        references.
    """
    int_to_ext_project_cache: dict[str, str | None] = {}

    def convert_ref(ref_str: str, embedded: bool) -> str:
        if ref_str.startswith(weave_internal_prefix):
            rest = ref_str[len(weave_internal_prefix) :]
            parts = rest.split("/", 1)
            if len(parts) != 2:
                raise InvalidInternalRef(f"Invalid URI: {ref_str}")
            project_id, tail = parts
            if project_id not in int_to_ext_project_cache:
                int_to_ext_project_cache[project_id] = convert_int_to_ext_project_id(
                    project_id
                )
            external_project_id = int_to_ext_project_cache[project_id]
            if not external_project_id:
                return f"{ri.WEAVE_PRIVATE_SCHEME}://///{tail}"
            return f"{ri.WEAVE_SCHEME}:///{external_project_id}/{tail}"
        # External ref stored where an internal one belongs. Embedded ones are
        # expected legacy state (writes only started converting inside JSON
        # strings mid-2026) and are already external-shaped, so they always
        # pass through; top-level ones raise unless the caller opted in.
        if not (embedded or tolerate_external_refs):
            raise InvalidInternalRef("Encountered unexpected ref format.")
        logger.error("Returning stored external ref unchanged: %s", ref_str)
        return ref_str

    return _map_values(obj, _make_ref_string_mapper(convert_ref))


E = TypeVar("E")


class _MapResult(NamedTuple):
    """Outcome of a single copy-on-write traversal step.

    value:           the (possibly new) value at this node.
    changed:         True if this subtree was rewritten; ancestors must clone.
    fast_path_safe:  False once we have seen a nested dataclass inside an
                     `Any` field. Models containing one have to fall back to
                     the legacy model_dump / model_validate path because
                     Pydantic does not round-trip dataclasses through
                     getattr / setattr.
    """

    value: Any
    changed: bool
    fast_path_safe: bool


def _map_values(obj: E, func: Callable[[E], E]) -> E:
    """Apply `func` to every scalar in `obj`, reusing untouched subtrees."""
    return cast(E, _walk(obj, cast(Callable[[Any], Any], func)).value)


def _walk(obj: Any, func: Callable[[Any], Any]) -> _MapResult:
    """Recursive copy-on-write dispatcher; one container kind per arm."""
    if isinstance(obj, BaseModel):
        return _walk_model(obj, func)
    if isinstance(obj, dict):
        return _walk_mapping(obj, func)
    if isinstance(obj, list):
        return _walk_sequence(obj, func, rebuild=list)
    if isinstance(obj, tuple):
        return _walk_sequence(obj, func, rebuild=tuple)
    if isinstance(obj, set):
        return _walk_set(obj, func)

    # Scalar leaf: ask the mapper for a replacement. Dataclasses are leaves
    # too, but trip the fast-path flag so any ancestor model knows to
    # round-trip via model_dump.
    new_obj = func(obj)
    if new_obj is not obj:
        return _MapResult(new_obj, True, True)
    return _MapResult(obj, False, not dataclasses.is_dataclass(obj))


def _walk_mapping(obj: dict, func: Callable[[Any], Any]) -> _MapResult:
    # Allocate a copy only on the first changed child, then write through it.
    clone: dict | None = None
    fast_path_safe = True
    for key, value in obj.items():
        result = _walk(value, func)
        if result.changed:
            if clone is None:
                clone = dict(obj)
            clone[key] = result.value
        fast_path_safe = fast_path_safe and result.fast_path_safe
    if clone is None:
        return _MapResult(obj, False, fast_path_safe)
    return _MapResult(clone, True, fast_path_safe)


def _walk_sequence(
    obj: Any,
    func: Callable[[Any], Any],
    rebuild: Callable[[list[Any]], Any],
) -> _MapResult:
    # Lists and tuples share an identical walk; only the final constructor
    # differs (`list` returns the buffer, `tuple` freezes it).
    clone: list[Any] | None = None
    fast_path_safe = True
    for index, value in enumerate(obj):
        result = _walk(value, func)
        if result.changed:
            if clone is None:
                clone = list(obj)
            clone[index] = result.value
        fast_path_safe = fast_path_safe and result.fast_path_safe
    if clone is None:
        return _MapResult(obj, False, fast_path_safe)
    return _MapResult(rebuild(clone), True, fast_path_safe)


def _walk_set(obj: set, func: Callable[[Any], Any]) -> _MapResult:
    # Sets have no useful index to write through, so we collect into a list
    # and rebuild only when something changed.
    values: list[Any] = []
    changed = False
    fast_path_safe = True
    for value in obj:
        result = _walk(value, func)
        values.append(result.value)
        changed = changed or result.changed
        fast_path_safe = fast_path_safe and result.fast_path_safe
    if not changed:
        return _MapResult(obj, False, fast_path_safe)
    return _MapResult(set(values), True, fast_path_safe)


def _walk_model(obj: BaseModel, func: Callable[[Any], Any]) -> _MapResult:
    """Walk a pydantic model with copy-on-write semantics.

    Three outcomes, in order:
      1. A subtree tripped `fast_path_safe=False` (nested dataclass that
         getattr/setattr can't round-trip cleanly) -> fall back to the
         legacy model_dump / _walk / model_validate path.
      2. Nothing changed -> return obj as-is, with one revalidation pass
         so `model_construct`-bypassed instances still get the same
         shape the legacy round-trip would have produced.
      3. Something changed -> apply updates and revalidate.
    """
    updates, fast_path_safe = _collect_model_updates(obj, func)

    if not fast_path_safe:
        return _MapResult(_model_via_roundtrip(obj, func), True, True)
    if not updates:
        return _MapResult(obj.__class__.model_validate(obj), False, True)
    return _MapResult(_apply_model_updates(obj, updates), True, True)


def _collect_model_updates(
    obj: BaseModel, func: Callable[[Any], Any]
) -> tuple[dict[str, Any], bool]:
    """Walk every declared field + every extra; collect what changed.

    `model_fields` covers declared fields. `model_extra` covers anything
    stashed by `extra='allow'` and is None for other models (so that
    loop is a no-op in the common case). Both sets of keys are merged
    into `updates` because setattr / model_copy(update=...) accept extra
    keys for `extra='allow'` models.
    """
    updates: dict[str, Any] = {}
    fast_path_safe = True

    for field_name, field_info in obj.__class__.model_fields.items():
        if field_info.exclude is True:
            continue
        result = _walk(getattr(obj, field_name), func)
        if result.changed:
            updates[field_name] = result.value
        fast_path_safe = fast_path_safe and result.fast_path_safe

    for extra_name, extra_value in (obj.model_extra or {}).items():
        result = _walk(extra_value, func)
        if result.changed:
            updates[extra_name] = result.value
        fast_path_safe = fast_path_safe and result.fast_path_safe

    return updates, fast_path_safe


def _apply_model_updates(obj: BaseModel, updates: dict[str, Any]) -> BaseModel:
    """Apply `updates` to `obj`. Frozen models get a copy; others mutate.

    Mutating in place preserves the outer model's identity so callers
    that hold the reference see the rewrite without an extra allocation.
    Either branch ends with model_validate so any pre-validation bypass
    via model_construct still gets the shape the legacy round-trip would
    have produced.
    """
    if obj.__class__.model_config.get("frozen"):
        updated = obj.model_copy(update=updates)
        return updated.__class__.model_validate(updated)

    for field_name, new_value in updates.items():
        setattr(obj, field_name, new_value)
    return obj.__class__.model_validate(obj)


def _model_via_roundtrip(obj: BaseModel, func: Callable[[Any], Any]) -> BaseModel:
    """Fallback used when a model contains a nested dataclass.

    `by_alias=True` is required: query models have Mongo-style aliased
    fields (e.g. `$gt`) whose internal property names cannot round-trip
    without it.
    """
    orig = obj.model_dump(by_alias=True)
    walked = _walk(orig, func)
    return obj.model_validate(walked.value)
