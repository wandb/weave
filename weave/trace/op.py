import inspect
import traceback
from functools import partial, wraps
from types import MethodType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Optional,
    Protocol,
    Union,
    cast,
    overload,
    runtime_checkable,
)

from weave import client_context
from weave.legacy import context_state
from weave.trace.call import _execute_call_async, _execute_call_sync, create_call
from weave.trace.refs import ObjectRef

if TYPE_CHECKING:
    from weave.weave_client import CallsIter


FinishCallbackType = Callable[[Any, Optional[BaseException]], None]
OnOutputHandlerType = Callable[[Any, FinishCallbackType, Dict], Any]


@runtime_checkable
class Op(Protocol):
    """
    The interface for Op-ified functions and methods.

    Op was previously a class, and has been converted to a Protocol to allow
    functions to pass for Op.  This is needed because many popular packages are
    using the `inspect` module for control flow, and Op instances don't always
    pass those checks.  In particular, `inspect.iscoroutinefunction` always
    fails for classes, even ones that implement async methods or protocols.

    Some of the attributes are carry-overs from when Op was a class.  We should
    consider removing the unnecessary ones where possible.
    - resolve_fn (I think you can just use the func itself?)
    - signature (just inspect the func)
    - _set_on_output_handler (does this have to be on the op?)
    - _on_output_handler (does this have to be on the op?)
    """

    name: str
    signature: inspect.Signature
    ref: Optional[ObjectRef]
    resolve_fn: Callable

    call: Callable[..., Any]
    calls: Callable[..., "CallsIter"]

    # not sure if this is the best place for this, but kept for compat
    _set_on_output_handler: Callable[[OnOutputHandlerType], None]
    _on_output_handler: Optional[OnOutputHandlerType]

    __call__: Callable[..., Any]
    __self__: Any


def _set_on_output_handler(func: Op, on_output: OnOutputHandlerType) -> None:
    if func._on_output_handler is not None:
        raise ValueError("Cannot set on_output_handler multiple times")
    func._on_output_handler = on_output


def _is_unbound_method(func: Callable) -> bool:
    """Check if a function is a function defined on a class (an "unbound" method)

    In python3, the "unbound" method is just a function, but that distinction is
    not enough for our decorator because it needs to operate on both regular funcs
    and unbound methods at the same time.

    This check clarifies that distinction between function vs. unbound method.
    """
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    is_method = params and params[0].name in {"self", "cls"}

    return bool(is_method)


def _call_sync(op: Op, *args: Any, **kwargs: Any) -> Any:
    _call = create_call(op, *args, **kwargs)
    try:
        return _execute_call_sync(op, _call, *args, **kwargs)
    except Exception as e:
        print("WARNING: Error executing call")
        traceback.print_exc()
    finally:
        return _call


async def _call_async(op: Op, *args: Any, **kwargs: Any) -> Any:
    _call = create_call(op, *args, **kwargs)
    try:
        return await _execute_call_async(op, _call, *args, **kwargs)
    except Exception as e:
        print("WARNING: Error executing call")
        traceback.print_exc()
    finally:
        return _call


def calls(op: Op) -> "CallsIter":
    client = client_context.weave_client.require_weave_client()
    return client._op_calls(op)


# Legacy decos
@overload
def op(name: Any) -> Any: ...
@overload
def op(input_type: Any, output_type: Any) -> Any: ...
@overload
def op(name: Any, input_type: Any, output_type: Any) -> Any: ...
@overload
def op(name: Any, output_type: Any) -> Any: ...
@overload
def op(name: Any, input_type: Any, output_type: Any, render_info: Any) -> Any: ...
@overload
def op(name: Any, input_type: Any, output_type: Any, pure: Any) -> Any: ...
@overload
def op(name: Any, input_type: Any, output_type: Any, hidden: Any) -> Any: ...
@overload
def op(
    input_type: Any = None,
    output_type: Any = None,
    refine_output_type: Any = None,
    name: Any = None,
    setter: Any = None,
    render_info: Any = None,
    hidden: Any = None,
    pure: Any = None,
    _op_def_class: Any = None,
    plugins: Any = None,
    mutation: Any = None,
    weavify: Any = None,
) -> Any: ...


# Modern decos
@overload
def op(func: Any) -> Op: ...


def op(*args: Any, **kwargs: Any) -> Union[Callable[[Any], Op], Op]:
    """
    A decorator to weave op-ify a function or method.  Works for both sync and async.

    Decorated functions and methods can be called as normal, but will also
    automatically track calls in the Weave UI.

    If you don't call `weave.init` then the function will behave as if it were
    not decorated.


    Example usage:
    ```
    import weave
    weave.init("my-project")

    @weave.op
    async def extract():
        return await client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {"role": "user", "content": "Create a user as JSON"},
            ],
        )

    await extract()  # calls the function and tracks the call in the Weave UI
    ```
    """
    if context_state.get_loading_built_ins():
        from weave.legacy.decorator_op import op as legacy_op

        return legacy_op(*args, **kwargs)  # type: ignore

    def op_deco(func: Callable) -> Op:
        # Check function type
        sig = inspect.signature(func)
        is_method = _is_unbound_method(func)
        is_async = inspect.iscoroutinefunction(func)

        def create_wrapper(func: Callable) -> Op:
            if is_async:

                @wraps(func)
                async def wrapper(*args: Any, **kwargs: Any) -> Any:
                    if client_context.weave_client.get_weave_client() is None:
                        return await func(*args, **kwargs)
                    call = create_call(wrapper, *args, **kwargs)  # type: ignore
                    return await _execute_call_async(wrapper, call, *args, **kwargs)  # type: ignore

                wrapper.call = partial(_call_async, wrapper)  # type: ignore
            else:

                @wraps(func)
                def wrapper(*args: Any, **kwargs: Any) -> Any:
                    if client_context.weave_client.get_weave_client() is None:
                        return func(*args, **kwargs)
                    call = create_call(wrapper, *args, **kwargs)  # type: ignore
                    return _execute_call_sync(wrapper, call, *args, **kwargs)  # type: ignore

                wrapper.call = partial(_call_sync, wrapper)  # type: ignore

            # Tack these helpers on to our wrapper
            wrapper.resolve_fn = func  # type: ignore

            name = func.__qualname__ if is_method else func.__name__

            # funcs and methods defined inside another func will have the
            # name prefixed with {outer}.<locals>.{func_name}
            # this is noisy for us, so we strip it out
            name = name.split(".<locals>.")[-1]

            wrapper.name = name  # type: ignore
            wrapper.signature = sig  # type: ignore
            wrapper.ref = None  # type: ignore

            wrapper.calls = partial(calls, wrapper)  # type: ignore

            wrapper.__call__ = wrapper  # type: ignore
            wrapper.__self__ = wrapper  # type: ignore

            wrapper._set_on_output_handler = partial(_set_on_output_handler, wrapper)  # type: ignore
            wrapper._on_output_handler = None  # type: ignore

            return cast(Op, wrapper)

        return create_wrapper(func)

    if len(args) == 1 and len(kwargs) == 0 and callable(func := args[0]):
        # return wrap(args[0])
        return op_deco(func)

    return op_deco


def maybe_bind_method(func: Callable, self: Any = None) -> Union[Callable, MethodType]:
    """Bind a function to any object (even if it's not a class)

    If self is None, return the function as is.
    """
    if (sig := inspect.signature(func)) and sig.parameters.get("self"):
        if inspect.ismethod(func) and id(func.__self__) != id(self):
            raise ValueError("Cannot re-bind a method to an new object")
        return MethodType(func, self)
    return func


def maybe_unbind_method(oplike: Union[Op, MethodType, partial]) -> Op:
    """Unbind an Op-like method or partial to a plain Op function.

    For:
    - methods, remove set `self` param
    - partials, remove any preset params
    """
    if isinstance(oplike, MethodType):
        op = oplike.__func__
    elif isinstance(oplike, partial):  # Handle cases op is defined as
        op = oplike.func
    else:
        op = oplike

    return cast(Op, op)
