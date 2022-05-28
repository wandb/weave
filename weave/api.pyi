from typing import Tuple, Union, Callable, Any, TypeVar

_T = TypeVar("_T")

# This adds VSCode/pylance/pyright typechecking support for weave.obj() using
# Data Class Transforms. See https://peps.python.org/pep-0681/.
def __dataclass_transform__(
    *,
    eq_default: bool = True,
    order_default: bool = False,
    kw_only_default: bool = False,
    field_descriptors: Tuple[Union[type, Callable[..., Any]], ...] = (()),
) -> Callable[[_T], _T]: ...
@__dataclass_transform__()
def type() -> Callable[[_T], _T]: ...
