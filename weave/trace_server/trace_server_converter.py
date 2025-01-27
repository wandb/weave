from typing import Callable, Optional, TypeVar, cast

from pydantic import BaseModel

from weave.trace_server import refs_internal as ri

A = TypeVar("A")
B = TypeVar("B")

weave_prefix = ri.WEAVE_SCHEME + ":///"
weave_internal_prefix = ri.WEAVE_INTERNAL_SCHEME + ":///"


class InvalidExternalRef(ValueError):
    pass


class InvalidInternalRef(ValueError):
    pass


def universal_ext_to_int_ref_converter(
    obj: A, convert_ext_to_int_project_id: Callable[[str], str]
) -> A:
    """Takes any object and recursively replaces all external references with
    internal references. The external references are expected to be in the
    format of `weave:///entity/project/...` and the internal references are
    expected to be in the format of `weave-trace-internal:///project_id/...`.

    Args:
        obj: The object to convert.
        convert_ext_to_int_project_id: A function that takes an external
            project ID and returns the internal project ID.

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
                return cast(B, replace_ref(obj))
            elif obj.startswith(weave_internal_prefix):
                # It is important to raise here as this would be the result of
                # an external client attempting to write internal refs directly.
                # We want to maintain full control over the internal refs.
                raise InvalidExternalRef("Encountered unexpected ref format.")
        return obj

    return _map_values(obj, mapper)


C = TypeVar("C")
D = TypeVar("D")


def universal_int_to_ext_ref_converter(
    obj: C,
    convert_int_to_ext_project_id: Callable[[str], Optional[str]],
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
    int_to_ext_project_cache: dict[str, Optional[str]] = {}

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
    if isinstance(obj, BaseModel):
        # `by_alias` is required since we have Mongo-style properties in the
        # query models that are aliased to conform to start with `$`. Without
        # this, the model_dump will use the internal property names which are
        # not valid for the `model_validate` step.
        orig = obj.model_dump(by_alias=True)
        new = _map_values(orig, func)
        return obj.model_validate(new)
    if isinstance(obj, dict):
        return cast(E, {k: _map_values(v, func) for k, v in obj.items()})
    if isinstance(obj, list):
        return cast(E, [_map_values(v, func) for v in obj])
    if isinstance(obj, tuple):
        return cast(E, tuple(_map_values(v, func) for v in obj))
    if isinstance(obj, set):
        return cast(E, {_map_values(v, func) for v in obj})
    return func(obj)
