"""Helpers for converting trace refs with copy-on-write traversal."""

import dataclasses
from collections.abc import Callable
from typing import Any, NamedTuple, TypeVar, cast

from pydantic import BaseModel

from weave.shared import refs_internal as ri
from weave.trace_server.errors import InvalidExternalRef

A = TypeVar("A")
B = TypeVar("B")

weave_prefix = ri.WEAVE_SCHEME + ":///"
weave_internal_prefix = ri.WEAVE_INTERNAL_SCHEME + ":///"


class InvalidInternalRef(ValueError):
    pass


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

    def replace_ref(ref_str: str) -> str:
        if not ref_str.startswith(weave_prefix):
            raise ValueError(f"Invalid URI: {ref_str}")
        rest = ref_str[len(weave_prefix) :]
        parts = rest.split("/", 2)
        if len(parts) != 3:
            raise InvalidExternalRef(f"Invalid URI: {ref_str}")
        entity, project, tail = parts
        project_key = f"{entity}/{project}"
        if project_key not in ext_to_int_project_cache:
            ext_to_int_project_cache[project_key] = convert_ext_to_int_project_id(
                project_key
            )
        internal_project_id = ext_to_int_project_cache[project_key]
        return f"{ri.WEAVE_INTERNAL_SCHEME}:///{internal_project_id}/{tail}"

    def mapper(obj: B) -> B:
        if isinstance(obj, str):
            if obj.startswith(weave_prefix):
                result = replace_ref(obj)
                return cast(B, result)
            elif obj.startswith(weave_internal_prefix):
                # Internal refs are only accepted when the verify callback
                # confirms the project_id is valid. Without this check, a
                # malicious client could embed refs to arbitrary private
                # projects.
                rest = obj[len(weave_internal_prefix) :]
                parts = rest.split("/", 2)
                if len(parts) < 2:
                    raise InvalidExternalRef(
                        "Invalid internal ref format: missing project_id or kind."
                    )
                ref_project_id = parts[0]
                if (
                    verify_internal_project_id is not None
                    and verify_internal_project_id(ref_project_id)
                ):
                    return obj
                raise InvalidExternalRef("Encountered unexpected internal ref format.")
        return obj

    return _map_values(obj, mapper)


C = TypeVar("C")
D = TypeVar("D")


def universal_int_to_ext_ref_converter(
    obj: C,
    convert_int_to_ext_project_id: Callable[[str], str | None],
) -> C:
    """Takes any object and recursively replaces all internal references with
    external references. The internal references are expected to be in the
    format of `weave-trace-internal:///project_id/...` and the external references are
    expected to be in the format of `weave:///entity/project/...`.

    Args:
        obj: The object to convert.
        convert_int_to_ext_project_id: A function that takes an internal
            project ID and returns the external project ID.

    Returns:
        The object with all internal references replaced with external
        references.
    """
    int_to_ext_project_cache: dict[str, str | None] = {}

    def replace_ref(ref_str: str) -> str:
        if not ref_str.startswith(weave_internal_prefix):
            raise ValueError(f"Invalid URI: {ref_str}")
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

    def mapper(obj: D) -> D:
        if isinstance(obj, str):
            if obj.startswith(weave_internal_prefix):
                return cast(D, replace_ref(obj))
            elif obj.startswith(weave_prefix):
                # It is important to raise here as this would be the result of
                # incorrectly storing an external ref at the database layer,
                # rather than an internal ref. There is a possibility in the
                # future that a programming error leads to this situation, in
                # which case reading this object would consistently fail. We
                # might want to instead return a private ref in this case.
                raise InvalidInternalRef("Encountered unexpected ref format.")
        return obj

    return _map_values(obj, mapper)


E = TypeVar("E")
F = TypeVar("F")


class _CopyOnWriteResult(NamedTuple):
    value: Any
    changed: bool
    fully_supported: bool


def _map_values(obj: E, func: Callable[[E], E]) -> E:
    """Recursively apply `func` while preserving untouched object identity."""
    return cast(E, _map_values_copy_on_write(obj, func).value)


def _map_values_copy_on_write(
    obj: E,
    func: Callable[[E], E],
) -> _CopyOnWriteResult:
    """Apply `func` recursively with copy-on-write traversal.

    `changed` means this branch was rewritten and callers must clone its ancestors.
    `fully_supported` means the fast path can preserve Pydantic model validation
    semantics. Dataclasses nested under models are handled safely by Pydantic's
    dump/validate path, so seeing one forces that fallback.
    """
    if isinstance(obj, BaseModel):
        return _map_model_values(obj, cast(Callable[[Any], Any], func))
    if isinstance(obj, dict):
        # Clone only after the first changed child.
        updated_dict: dict[Any, Any] | None = None
        fully_supported = True
        for key, value in obj.items():
            result = _map_values_copy_on_write(value, func)
            if result.changed:
                if updated_dict is None:
                    updated_dict = dict(obj)
                updated_dict[key] = result.value
            fully_supported = fully_supported and result.fully_supported
        if updated_dict is None:
            return _CopyOnWriteResult(obj, False, fully_supported)
        return _CopyOnWriteResult(cast(E, updated_dict), True, fully_supported)
    if isinstance(obj, list):
        # Same copy-on-write rule for lists.
        updated_list: list[Any] | None = None
        fully_supported = True
        for index, value in enumerate(obj):
            result = _map_values_copy_on_write(value, func)
            if result.changed:
                if updated_list is None:
                    updated_list = list(obj)
                updated_list[index] = result.value
            fully_supported = fully_supported and result.fully_supported
        if updated_list is None:
            return _CopyOnWriteResult(obj, False, fully_supported)
        return _CopyOnWriteResult(cast(E, updated_list), True, fully_supported)
    if isinstance(obj, tuple):
        # Buffer tuple updates and rebuild only if something changed.
        updated_items: list[Any] | None = None
        fully_supported = True
        for index, value in enumerate(obj):
            result = _map_values_copy_on_write(value, func)
            if result.changed:
                if updated_items is None:
                    updated_items = list(obj)
                updated_items[index] = result.value
            fully_supported = fully_supported and result.fully_supported
        if updated_items is None:
            return _CopyOnWriteResult(obj, False, fully_supported)
        return _CopyOnWriteResult(cast(E, tuple(updated_items)), True, fully_supported)
    if isinstance(obj, set):
        # Sets rebuild on change, but still skip allocation on no-op paths.
        values = []
        changed = False
        fully_supported = True
        for value in obj:
            result = _map_values_copy_on_write(value, func)
            values.append(result.value)
            changed = changed or result.changed
            fully_supported = fully_supported and result.fully_supported
        if not changed:
            return _CopyOnWriteResult(obj, False, fully_supported)
        return _CopyOnWriteResult(cast(E, set(values)), True, fully_supported)

    new_obj = func(obj)
    if new_obj is not obj:
        return _CopyOnWriteResult(new_obj, True, True)
    return _CopyOnWriteResult(new_obj, False, not dataclasses.is_dataclass(obj))


def _map_model_values(
    obj: BaseModel,
    func: Callable[[Any], Any],
) -> _CopyOnWriteResult:
    """Rewrite model fields in place when possible.

    Frozen models use `model_copy`. Nested dataclasses fall back to
    dump/validate.
    """
    updates: dict[str, Any] = {}
    fully_supported = True
    for field_name, field_info in obj.__class__.model_fields.items():
        if field_info.exclude is True:
            continue
        current_value = getattr(obj, field_name)
        result = _map_values_copy_on_write(current_value, func)
        if result.changed:
            updates[field_name] = result.value
        fully_supported = fully_supported and result.fully_supported

    if not fully_supported:
        # Nested dataclasses force the old dump/validate fallback.
        return _CopyOnWriteResult(
            _map_model_values_with_roundtrip(obj, func), True, True
        )

    if not updates:
        # Revalidate the existing instance so callers that intentionally
        # bypassed model validation with `model_construct(...)` still see the
        # same validation behavior without paying for a full dump/rebuild.
        return _CopyOnWriteResult(obj.__class__.model_validate(obj), False, True)

    if obj.__class__.model_config.get("frozen"):
        updated_obj = obj.model_copy(update=updates)
        return _CopyOnWriteResult(
            updated_obj.__class__.model_validate(updated_obj), True, True
        )

    # Mutating non-frozen models is intentional: callers keep the outer model
    # identity and only changed fields are replaced.
    for field_name, new_value in updates.items():
        setattr(obj, field_name, new_value)
    return _CopyOnWriteResult(obj.__class__.model_validate(obj), True, True)


def _map_model_values_with_roundtrip(
    obj: BaseModel,
    func: Callable[[Any], Any],
) -> BaseModel:
    """Fallback path for models that contain unsupported nested dataclasses."""
    # `by_alias` is required since we have Mongo-style properties in the
    # query models that are aliased to conform to start with `$`. Without
    # this, the model_dump will use the internal property names which are
    # not valid for the `model_validate` step.
    orig = obj.model_dump(by_alias=True)
    result = _map_values_copy_on_write(orig, func)
    return obj.model_validate(result.value)
