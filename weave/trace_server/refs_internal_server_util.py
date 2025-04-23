from typing import Optional, TypeVar, Union, overload

from weave.trace_server import refs_internal as ri
from weave.trace_server.errors import InvalidRequest

T = TypeVar(
    "T", ri.InternalObjectRef, ri.InternalTableRef, ri.InternalCallRef, ri.InternalOpRef
)


@overload
def ensure_ref_is_valid(
    ref: str, expected_type: None = None
) -> Union[ri.InternalObjectRef, ri.InternalTableRef, ri.InternalCallRef]: ...


@overload
def ensure_ref_is_valid(
    ref: str,
    expected_type: tuple[type[T], ...],
) -> T: ...


def ensure_ref_is_valid(
    ref: str, expected_type: Optional[tuple[type, ...]] = None
) -> ri.InternalRef:
    """Validates and parses an internal URI reference.

    Args:
        ref: The reference string to validate
        expected_type: Optional tuple of expected reference types

    Returns:
        The parsed internal reference object

    Raises:
        InvalidRequest: If the reference is invalid or doesn't match expected_type
    """
    try:
        parsed_ref = ri.parse_internal_uri(ref)
    except ValueError as e:
        raise InvalidRequest(f"Invalid ref: {ref}, {e}")
    if expected_type and not isinstance(parsed_ref, expected_type):
        raise InvalidRequest(
            f"Invalid ref: {ref}, expected {(t.__name__ for t in expected_type)}"
        )
    return parsed_ref
