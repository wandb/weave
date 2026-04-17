import dataclasses
from collections.abc import Callable
from typing import Any, TypeVar, cast

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


def _map_values(obj: E, func: Callable[[E], E]) -> E:
    new_obj, _, _ = _map_values_copy_on_write(obj, func)
    return cast(E, new_obj)


def _map_values_copy_on_write(
    obj: E,
    func: Callable[[E], E],
) -> tuple[E, bool, bool]:
    if isinstance(obj, BaseModel):
        return _map_model_values(obj, func)
    if isinstance(obj, dict):
        updated_dict: dict[Any, Any] | None = None
        fully_supported = True
        for key, value in obj.items():
            new_value, changed, supported = _map_values_copy_on_write(value, func)
            if changed:
                if updated_dict is None:
                    updated_dict = dict(obj)
                updated_dict[key] = new_value
            fully_supported = fully_supported and supported
        if updated_dict is None:
            return obj, False, fully_supported
        return cast(E, updated_dict), True, fully_supported
    if isinstance(obj, list):
        updated_list: list[Any] | None = None
        fully_supported = True
        for index, value in enumerate(obj):
            new_value, changed, supported = _map_values_copy_on_write(value, func)
            if changed:
                if updated_list is None:
                    updated_list = list(obj)
                updated_list[index] = new_value
            fully_supported = fully_supported and supported
        if updated_list is None:
            return obj, False, fully_supported
        return cast(E, updated_list), True, fully_supported
    if isinstance(obj, tuple):
        updated_items: list[Any] | None = None
        fully_supported = True
        for index, value in enumerate(obj):
            new_value, changed, supported = _map_values_copy_on_write(value, func)
            if changed:
                if updated_items is None:
                    updated_items = list(obj)
                updated_items[index] = new_value
            fully_supported = fully_supported and supported
        if updated_items is None:
            return obj, False, fully_supported
        return cast(E, tuple(updated_items)), True, fully_supported
    if isinstance(obj, set):
        values = []
        changed = False
        fully_supported = True
        for value in obj:
            new_value, value_changed, supported = _map_values_copy_on_write(value, func)
            values.append(new_value)
            changed = changed or value_changed
            fully_supported = fully_supported and supported
        if not changed:
            return obj, False, fully_supported
        return cast(E, set(values)), True, fully_supported

    new_obj = func(obj)
    if new_obj is not obj:
        return new_obj, True, True
    return new_obj, False, not dataclasses.is_dataclass(obj)


def _map_model_values(
    obj: BaseModel,
    func: Callable[[Any], Any],
) -> tuple[BaseModel, bool, bool]:
    updates: dict[str, Any] = {}
    fully_supported = True
    for field_name, field_info in obj.__class__.model_fields.items():
        if field_info.exclude is True:
            continue
        current_value = getattr(obj, field_name)
        new_value, changed, supported = _map_values_copy_on_write(current_value, func)
        if changed:
            updates[field_name] = new_value
        fully_supported = fully_supported and supported

    if not fully_supported:
        return _map_model_values_with_roundtrip(obj, func), True, True

    if not updates:
        return obj, False, True

    if obj.__class__.model_config.get("frozen"):
        return obj.model_copy(update=updates), True, True

    for field_name, new_value in updates.items():
        setattr(obj, field_name, new_value)
    return obj, True, True


def _map_model_values_with_roundtrip(
    obj: BaseModel,
    func: Callable[[Any], Any],
) -> BaseModel:
    # `by_alias` is required since we have Mongo-style properties in the
    # query models that are aliased to conform to start with `$`. Without
    # this, the model_dump will use the internal property names which are
    # not valid for the `model_validate` step.
    orig = obj.model_dump(by_alias=True)
    new_obj, _, _ = _map_values_copy_on_write(orig, func)
    return obj.model_validate(new_obj)
