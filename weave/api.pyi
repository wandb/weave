from typing import Tuple, Union, Callable, Any, TypeVar

# Because we are going to declare weave.type, but we need to call
# Python's type.
_pytype = type

_T = TypeVar("_T")

# This adds VSCode/pylance/pyright typechecking support for weave.obj() using
# Data Class Transforms. See https://peps.python.org/pep-0681/.
def __dataclass_transform__(
    *,
    eq_default: bool = True,
    order_default: bool = False,
    kw_only_default: bool = False,
    field_descriptors: Tuple[Union[_pytype, Callable[..., Any]], ...] = (()),
) -> Callable[[_T], _T]: ...
@__dataclass_transform__()
def type() -> Callable[[_T], _T]: ...

from . import weave_types as types
from . import errors
from .decorators import weave_class, op, mutation, type
from .op_args import OpVarArgs
from . import usage_analytics
from .context import (
    use_fixed_server_port,
    use_frontend_devmode,
    capture_weave_server_logs,
    eager_execution,
)

from .weave_internal import define_fn
