from collections.abc import Callable
from typing import TypeVar, cast

from pydantic import BaseModel

from weave.trace_server import refs_internal as ri
from weave.trace_server.errors import InvalidExternalRef

A = TypeVar("A")
B = TypeVar("B")

weave_prefix = ri.WEAVE_SCHEME + ":///"
weave_internal_prefix = ri.WEAVE_INTERNAL_SCHEME + ":///"


class InvalidInternalRef(ValueError):
    pass


def _extract_project_from_internal_ref(ref_str: str) -> str:
    """Extract the project_id from an internal ref string.

    Args:
        ref_str: Internal ref in format weave-trace-internal:///project_id/...

    Returns:
        The project_id.

    Raises:
        InvalidExternalRef: If the ref format is invalid.
    """
    if not ref_str.startswith(weave_internal_prefix):
        raise InvalidExternalRef(f"Invalid internal ref: {ref_str}")
    rest = ref_str[len(weave_internal_prefix) :]
    parts = rest.split("/", 1)
    if len(parts) < 1 or not parts[0]:
        raise InvalidExternalRef(f"Invalid internal ref format: {ref_str}")
    return parts[0]


def universal_ext_to_int_ref_converter(
    obj: A,
    convert_ext_to_int_project_id: Callable[[str], str],
    validate_internal_project_access: Callable[[str], bool] | None = None,
) -> A:
    """Takes any object and recursively replaces all external references with
    internal references. The external references are expected to be in the
    format of `weave:///entity/project/...` and the internal references are
    expected to be in the format of `weave-trace-internal:///project_id/...`.

    If validate_internal_project_access is provided, internal refs from the
    client are accepted if the validation callback returns True for the
    project_id in the ref. This enables client-side digest calculation.

    Args:
        obj: The object to convert.
        convert_ext_to_int_project_id: A function that takes an external
            project ID and returns the internal project ID.
        validate_internal_project_access: Optional callback to validate that
            the authenticated user has read access to the project_id in an
            internal ref. If None, internal refs from clients are rejected.

    Returns:
        The object with all external references replaced with internal
        references.
    """
    ext_to_int_project_cache: dict[str, str] = {}
    validated_project_ids: set[str] = set()

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

    def validate_and_pass_internal_ref(ref_str: str) -> str:
        """Validate and pass through an internal ref from the client."""
        project_id = _extract_project_from_internal_ref(ref_str)

        # Cache validation results to avoid repeated checks
        if project_id not in validated_project_ids:
            if validate_internal_project_access is None:
                raise InvalidExternalRef(
                    "Internal refs not allowed from client (server does not support validation)"
                )
            if not validate_internal_project_access(project_id):
                raise InvalidExternalRef(
                    f"No read access to project in ref: {project_id}"
                )
            validated_project_ids.add(project_id)

        return ref_str

    def mapper(obj: B) -> B:
        if isinstance(obj, str):
            if obj.startswith(weave_prefix):
                return cast(B, replace_ref(obj))
            elif obj.startswith(weave_internal_prefix):
                # Client is sending internal refs directly - validate access
                if validate_internal_project_access is not None:
                    return cast(B, validate_and_pass_internal_ref(obj))
                # No validation callback - reject internal refs (legacy behavior)
                raise InvalidExternalRef("Encountered unexpected ref format.")
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
