import typing

from pydantic import BaseModel

from . import refs_internal as ri


def universal_ext_to_int_ref_converter(obj: typing.Any, convert_ext_to_int_project_id: typing.Callable[[str], str]) -> typing.Any:
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
    ext_to_int_project_cache: typing.Dict[str, str] = {}
    weave_prefix = ri.WEAVE_SCHEME + ":///"

    def replace_ref(ref_str: str) -> str:
        if not ref_str.startswith(weave_prefix):
            raise ValueError(f"Invalid URI: {ref_str}")
        rest = ref_str[len(weave_prefix) :]
        parts = rest.split("/", 2)
        if len(parts) != 3:
            raise ValueError(f"Invalid URI: {ref_str}")
        entity, project, tail = parts
        project_key = f"{entity}/{project}"
        if project_key not in ext_to_int_project_cache:
            ext_to_int_project_cache[project_key] = convert_ext_to_int_project_id(project_key)
        internal_project_id = ext_to_int_project_cache[project_key]
        return f"{ri.WEAVE_INTERNAL_SCHEME}:///{internal_project_id}/{tail}"

    def mapper(obj: typing.Any) -> typing.Any:
        if isinstance(obj, str) and obj.startswith(weave_prefix):
            return replace_ref(obj)
        return obj

    return _map_values(obj, mapper)


def universal_int_to_ext_ref_converter(
    obj: typing.Any,
    convert_int_to_ext_project_id: typing.Callable[[str], str],
) -> typing.Any:
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
    int_to_ext_project_cache: dict[str, str] = {}

    weave_internal_prefix = ri.WEAVE_INTERNAL_SCHEME + ":///"

    def replace_ref(ref_str: str) -> str:
        if not ref_str.startswith(weave_internal_prefix):
            raise ValueError(f"Invalid URI: {ref_str}")
        rest = ref_str[len(weave_internal_prefix) :]
        parts = rest.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid URI: {ref_str}")
        project_id, tail = parts
        if project_id not in int_to_ext_project_cache:
            int_to_ext_project_cache[project_id] = convert_int_to_ext_project_id(project_id)
        external_project_id = int_to_ext_project_cache[project_id]
        return f"{ri.WEAVE_SCHEME}:///{external_project_id}/{tail}"

    def mapper(obj: typing.Any) -> typing.Any:
        if isinstance(obj, str) and obj.startswith(weave_internal_prefix):
            return replace_ref(obj)
        return obj

    return _map_values(obj, mapper)


def _map_values(obj: typing.Any, func: typing.Callable[[typing.Any], typing.Any]) -> typing.Any:
    if isinstance(obj, BaseModel):
        # `by_alias` is required since we have Mongo-style properties in the
        # query models that are aliased to conform to start with `$`. Without
        # this, the model_dump will use the internal property names which are
        # not valid for the `model_validate` step.
        orig = obj.model_dump(by_alias=True)
        new = _map_values(orig, func)
        return obj.model_validate(new)
    if isinstance(obj, dict):
        return {k: _map_values(v, func) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_map_values(v, func) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_map_values(v, func) for v in obj)
    if isinstance(obj, set):
        return {_map_values(v, func) for v in obj}
    return func(obj)
