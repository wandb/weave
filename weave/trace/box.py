"""Alternate boxing implementation for Weave Trace.

This copies many things from query service's box.py, but it notably
does not box None and bool which simplify checks for trace users."""

from __future__ import annotations

import datetime
from typing import Any, TypeVar, TYPE_CHECKING

if TYPE_CHECKING:
    from numpy import array, asarray, ndarray
    _NUMPY_AVAILABLE = True
else:
    try:
        from weave.utils.lazy_import import get_numpy
        _NUMPY_AVAILABLE = True
    except ImportError:
        _NUMPY_AVAILABLE = False
        get_numpy = None

from weave.trace.refs import Ref

T = TypeVar("T")


class BoxedInt(int):
    _id: int | None = None
    ref: Ref | None = None


class BoxedFloat(float):
    _id: int | None = None
    ref: Ref | None = None


class BoxedStr(str):
    _id: int | None = None
    ref: Ref | None = None


class BoxedDatetime(datetime.datetime):
    ref: Ref | None = None

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, datetime.datetime)
            and self.timestamp() == other.timestamp()
        )


class BoxedTimedelta(datetime.timedelta):
    ref: Ref | None = None

    def __eq__(self, other: Any) -> bool:
        return (
            isinstance(other, datetime.timedelta)
            and self.total_seconds() == other.total_seconds()
        )


# See https://numpy.org/doc/stable/user/basics.subclassing.html
def _create_boxed_ndarray_class():
    """Create BoxedNDArray class with numpy imported lazily."""
    if not _NUMPY_AVAILABLE:
        # Define a placeholder class when numpy is not available
        class BoxedNDArray:  # type: ignore[no-redef]
            ref: Ref | None = None

            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise ImportError("numpy is required for BoxedNDArray but is not installed")
        return BoxedNDArray
    
    # Import numpy lazily
    np = get_numpy()
    
    class BoxedNDArray(np.ndarray):  # pyright: ignore[reportRedeclaration]
        ref: Ref | None = None

        def __new__(cls, input_array: Any) -> BoxedNDArray:
            obj = np.asarray(input_array).view(cls)
            return obj

        def __array_finalize__(self, obj: Any) -> None:
            if obj is None:
                return
    
    return BoxedNDArray

# Create the class lazily - will import numpy only when this is actually accessed
_boxed_ndarray_class = None

def _get_boxed_ndarray_class():
    """Get BoxedNDArray class, creating it lazily if needed."""
    global _boxed_ndarray_class
    if _boxed_ndarray_class is None:
        _boxed_ndarray_class = _create_boxed_ndarray_class()
    return _boxed_ndarray_class

# For type checking and backward compatibility
if TYPE_CHECKING:
    from numpy import ndarray
    class BoxedNDArray(ndarray):  # type: ignore
        ref: Ref | None = None
else:
    # This will be a lazy property that creates the class when accessed
    class _LazyBoxedNDArray:
        def __call__(self, *args, **kwargs):
            return _get_boxed_ndarray_class()(*args, **kwargs)
        
        def __instancecheck__(self, instance):
            return isinstance(instance, _get_boxed_ndarray_class())
    
    BoxedNDArray = _LazyBoxedNDArray()


def box(
    obj: T,
) -> (
    T | BoxedInt | BoxedFloat | BoxedStr | BoxedNDArray | BoxedDatetime | BoxedTimedelta
):
    """
    Box an object to add reference tracking capabilities.

    Args:
        obj: The object to box.

    Returns:
        The boxed object with reference tracking capabilities, or the original object if boxing is not supported.

    Examples:
        >>> box(42)
        42
        >>> box("hello")
        'hello'
        >>> box(3.14)
        3.14
    """
    if type(obj) == int:
        return BoxedInt(obj)
    elif type(obj) == float:
        return BoxedFloat(obj)
    elif type(obj) == str:
        return BoxedStr(obj)
    elif _NUMPY_AVAILABLE and get_numpy is not None and type(obj) == get_numpy().ndarray:
        return BoxedNDArray(obj)
    elif type(obj) == datetime.datetime:
        return BoxedDatetime.fromtimestamp(obj.timestamp(), tz=datetime.timezone.utc)
    elif type(obj) == datetime.timedelta:
        return BoxedTimedelta(seconds=obj.total_seconds())
    return obj


def unbox(
    obj: T,
) -> T | int | float | str | 'ndarray' | datetime.datetime | datetime.timedelta:
    """
    Unbox an object to get the underlying value.

    Args:
        obj: The object to unbox.

    Returns:
        The unboxed object, or the original object if unboxing is not needed.

    Examples:
        >>> unbox(BoxedInt(42))
        42
        >>> unbox(BoxedStr("hello"))
        'hello'
        >>> unbox(BoxedFloat(3.14))
        3.14
    """
    if type(obj) == BoxedInt:
        return int(obj)
    elif type(obj) == BoxedFloat:
        return float(obj)
    elif type(obj) == BoxedStr:
        return str(obj)
    elif _NUMPY_AVAILABLE and type(obj) == _get_boxed_ndarray_class():
        return get_numpy().array(obj)
    elif type(obj) == BoxedDatetime:
        return datetime.datetime.fromtimestamp(obj.timestamp())
    elif type(obj) == BoxedTimedelta:
        return datetime.timedelta(seconds=obj.total_seconds())
    return obj
