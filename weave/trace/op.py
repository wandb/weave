import inspect
import typing
from functools import partial, wraps
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    Literal,
    Mapping,
    Optional,
    Protocol,
    TypeVar,
    Union,
    cast,
    overload,
    runtime_checkable,
)

from typing_extensions import ParamSpec

from weave import call_context, client_context
from weave.legacy import box, context_state
from weave.trace.constants import TRACE_CALL_EMOJI
from weave.trace.context import call_attributes
from weave.trace.errors import OpCallError
from weave.trace.refs import ObjectRef

from .constants import TRACE_CALL_EMOJI

T = TypeVar("T", bound=Callable[..., Any])

if TYPE_CHECKING:
    from weave.weave_client import Call, CallsIter

try:
    from openai._types import NOT_GIVEN as OPENAI_NOT_GIVEN
except ImportError:
    OPENAI_NOT_GIVEN = None


def print_call_link(call: "Call") -> None:
    print(f"{TRACE_CALL_EMOJI} {call.ui_url}")


FinishCallbackType = Callable[[Any, Optional[BaseException]], None]
OnOutputHandlerType = Callable[[Any, FinishCallbackType, Dict], Any]


class Op:
    resolve_fn: Callable
    # `_on_output_handler` is an experimental API and may change in the future
    # intended for use by internal Weave code. Specifically, it is used to set a
    # callback that will be called when the output of the op is available. This
    # handler is passed two values: the output of the op and a finish callback
    # that should be called with the output of the op. The handler should return
    # the value it wishes to send back to the user. The finish callback should
    # be called exactly once and can optionally take an exception as a second
    # argument to indicate an error. If the finish callback is not called, the
    # op will not finish and the call will not complete. This is useful for cases
    # where the output of the op is not immediately available or the op needs to
    # do some processing before it can be returned. If we decide to make this a
    # public API, we will likely add this to the constructor of the op. For now
    # it can be set using the `_set_on_output_handler` method.
    _on_output_handler: Optional[OnOutputHandlerType] = None
    # double-underscore to avoid conflict with old Weave refs
    __ref: Optional[ObjectRef] = None

    def __init__(self, resolve_fn: Callable) -> None:
        self.resolve_fn = resolve_fn
        self.name = resolve_fn.__name__
        self.signature = inspect.signature(resolve_fn)
        self._on_output_handler = None

    def __get__(
        self, obj: Optional[object], objtype: Optional[type[object]] = None
    ) -> "BoundOp":
        return BoundOp(obj, objtype, self)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        maybe_client = client_context.weave_client.get_weave_client()
        if maybe_client is None:
            return self.resolve_fn(*args, **kwargs)

        call = self._create_call(*args, **kwargs)
        return self._execute_call(call, *args, **kwargs)

    def _create_call(self, *args: Any, **kwargs: Any) -> Any:
        client = client_context.weave_client.require_weave_client()

        print(f"Inside _create_call, {self=}, {args=}, {kwargs=}")

        try:
            inputs = self.signature.bind(*args, **kwargs).arguments
            # print(f"{inputs=}")
        except TypeError as e:
            raise OpCallError(f"Error calling {self.name}: {e}")
        inputs_with_defaults = _apply_fn_defaults_to_inputs(self.resolve_fn, inputs)

        # If/When we do memoization, this would be a good spot

        parent_call = call_context.get_current_call()
        client._save_nested_objects(inputs_with_defaults)
        attributes = call_attributes.get()

        return client.create_call(
            self,
            inputs_with_defaults,
            parent_call,
            attributes=attributes,
        )

    def _execute_call(self, call: Any, *args: Any, **kwargs: Any) -> Any:
        client = client_context.weave_client.require_weave_client()
        has_finished = False

        def finish(
            output: Any = None, exception: Optional[BaseException] = None
        ) -> None:
            nonlocal has_finished
            if has_finished:
                raise ValueError("Should not call finish more than once")
            client.finish_call(call, output, exception)
            if not call_context.get_current_call():
                print_call_link(call)

        def on_output(output: Any) -> Any:
            if self._on_output_handler:
                return self._on_output_handler(output, finish, call.inputs)
            finish(output)
            return output

        try:
            res = self.resolve_fn(*args, **kwargs)
            # TODO: can we get rid of this?
            res = box.box(res)
        except BaseException as e:
            finish(exception=e)
            raise
        # We cannot let BoxedNone or BoxedBool escape into the user's code
        # since they cannot pass instance checks for None or bool.
        if isinstance(res, box.BoxedNone):
            res = None
        if isinstance(res, box.BoxedBool):
            res = res.val
        if inspect.iscoroutine(res):

            async def _call_async() -> Coroutine[Any, Any, Any]:
                try:
                    awaited_res = res
                    call_context.push_call(call)
                    output = await awaited_res
                    return on_output(output)
                except BaseException as e:
                    finish(exception=e)
                    raise

            call_context.pop_call(call.id)
            return _call_async()
        else:
            return on_output(res)

    def call(self, *args: Any, **kwargs: Any) -> "Call":
        _call = self._create_call(*args, **kwargs)
        self._execute_call(_call, *args, **kwargs)
        return _call

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"

    @property
    def ref(self) -> Optional[ObjectRef]:
        return self.__ref

    @ref.setter
    def ref(self, ref: ObjectRef) -> None:
        self.__ref = ref

    def calls(self) -> "CallsIter":
        client = client_context.weave_client.require_weave_client()
        return client._op_calls(self)

    def _set_on_output_handler(self, on_output: OnOutputHandlerType) -> None:
        """This is an experimental API and may change in the future intended for use by internal Weave code."""
        if self._on_output_handler is not None:
            raise ValueError("Cannot set on_output_handler multiple times")
        self._on_output_handler = on_output


class BoundOp(Op):
    arg0: Any
    op: Op

    def __init__(
        self, arg0: object, arg0_class: Optional[type[object]], op: Op
    ) -> None:
        self.arg0 = arg0
        self.op = op  # type: ignore

        # A bit hacky, but we want to use the name if
        # it was explicitly set by the user
        name_is_custom = op.name != op.resolve_fn.__name__

        if name_is_custom:
            self.name = op.name
        elif arg0_class is None:
            self.name = op.resolve_fn.__name__
        else:
            self.name = arg0_class.__name__ + "." + op.resolve_fn.__name__
        self.signature = inspect.signature(op.resolve_fn)
        self.resolve_fn = op.resolve_fn
        self._on_output_handler = op._on_output_handler

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return Op.__call__(self, self.arg0, *args, **kwargs)

    @property
    def ref(self) -> Optional[ObjectRef]:
        # return self.op.__ref
        return self.op.ref

    @ref.setter
    def ref(self, ref: ObjectRef) -> None:
        # self.op.__ref = ref
        self.op.ref = ref


P = ParamSpec("P")
R = TypeVar("R")


# The decorator!
# def op(*args: Any, **kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
#     if context_state.get_loading_built_ins():
#         from weave.legacy.decorator_op import op

#         return op(*args, **kwargs)

#     # def wrap(f: Callable[P, R]) -> Callable[P, R]:
#     #     op = Op(f)
#     #     functools.update_wrapper(op, f)
#     #     return op  # type: ignore

#     if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
#         # return wrap(args[0])
#         return op2(args[0])

#     return op2


def value_is_sentinel(param: Any) -> bool:
    return param.default is None or param.default is OPENAI_NOT_GIVEN


def _apply_fn_defaults_to_inputs(
    fn: typing.Callable, inputs: Mapping[str, typing.Any]
) -> dict[str, typing.Any]:
    inputs = {**inputs}
    sig = inspect.signature(fn)
    for param_name, param in sig.parameters.items():
        if param_name not in inputs:
            if param.default != inspect.Parameter.empty and not value_is_sentinel(
                param
            ):
                inputs[param_name] = param.default
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                inputs[param_name] = tuple()
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                inputs[param_name] = dict()
    return inputs


@runtime_checkable
class Op2(Protocol):
    name: str
    signature: inspect.Signature
    ref: Optional[ObjectRef]
    resolve_fn: Callable

    call: Callable[..., Any]
    calls: Callable[..., "CallsIter"]

    # this should not be here but kept for simplicity for now
    _set_on_output_handler: Callable[[OnOutputHandlerType], None]
    _on_output_handler: Optional[OnOutputHandlerType]

    __call__: Callable[..., Any]
    __self__: Any


def _set_on_output_handler(func: Op2, on_output: OnOutputHandlerType) -> None:
    if func._on_output_handler is not None:
        raise ValueError("Cannot set on_output_handler multiple times")
    func._on_output_handler = on_output


def _is_method_alt(func: Callable) -> bool:
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    is_method = params and params[0].name in {"self", "cls"}

    return bool(is_method)


def _create_call(func: Op2, *args: Any, **kwargs: Any) -> "Call":
    client = client_context.weave_client.require_weave_client()

    # is_method2 = _is_method_alt(func)
    # is_method = inspect.ismethod(func)
    # print(f"{is_method=}")
    # if is_method:
    #     self = func.__self__
    #     args = (self,) + args

    # if not is_method and is_method2:
    #     self = func.__self__
    #     args = (self,) + args

    print(f"{func=}, {args=}, {kwargs=}")

    try:
        inputs = func.signature.bind(*args, **kwargs).arguments
        # print(f"{inputs=}")
    except TypeError as e:
        raise OpCallError(f"Error calling {func.name}: {e}")
    inputs_with_defaults = _apply_fn_defaults_to_inputs(func, inputs)

    # This should probably be configurable, but for now we redact the api_key
    if "api_key" in inputs_with_defaults:
        inputs_with_defaults["api_key"] = "REDACTED"

    # If/When we do memoization, this would be a good spot

    parent_call = call_context.get_current_call()
    client._save_nested_objects(inputs_with_defaults)
    attributes = call_attributes.get()

    print(
        f"about to call client.create_call with {func=}, {inputs_with_defaults=}, {parent_call=}, {attributes=}"
    )

    return client.create_call(
        func,
        inputs_with_defaults,
        parent_call,
        attributes=attributes,
    )


def _execute_call(
    wrapper: Op2,
    call: Any,
    *args: Any,
    return_type: Literal["call", "value"] = "call",
    **kwargs: Any,
) -> Any:
    func = wrapper.resolve_fn
    print(f"Before call {func=}")
    client = client_context.weave_client.require_weave_client()
    has_finished = False

    def finish(output: Any = None, exception: Optional[BaseException] = None) -> None:
        print("start finish")
        nonlocal has_finished
        if has_finished:
            raise ValueError("Should not call finish more than once")
        client.finish_call(call, output, exception)
        if not call_context.get_current_call():
            print_call_link(call)

    def on_output(output: Any) -> Any:
        print("start on_output")
        if handler := getattr(wrapper, "_on_output_handler", None):
            print(f"Calling the handler {handler=}")
            return handler(output, finish, call.inputs)
        finish(output)
        return output

    try:
        res = func(*args, **kwargs)
    except BaseException as e:
        finish(exception=e)
        raise
    else:
        res = box.box(res)  # TODO: can we get rid of this?
    # We cannot let BoxedNone or BoxedBool escape into the user's code
    # since they cannot pass instance checks for None or bool.
    if isinstance(res, box.BoxedNone):
        res = None
    if isinstance(res, box.BoxedBool):
        res = res.val

    if inspect.iscoroutine(res):
        awaitable = res

        async def _call_async() -> Coroutine[Any, Any, Any]:
            try:
                call_context.push_call(call)
                output = await awaitable
                res2 = on_output(output)
                return call if return_type == "call" else res2
            except BaseException as e:
                finish(exception=e)
                raise
            finally:
                call_context.pop_call(call.id)

        return _call_async()
    else:
        res2 = on_output(res)
        return call if return_type == "call" else res2


def call(func: Op2, *args: Any, **kwargs: Any) -> Any:
    # There is probably a better place for this
    if _is_method_alt(func):
        self = func.__self__
        args = (self,) + args
    c = _create_call(func, *args, **kwargs)
    res = _execute_call(func, c, *args, **kwargs)
    return res


def calls(func: Op2) -> "CallsIter":
    client = client_context.weave_client.require_weave_client()
    return client._op_calls(func)


@overload
def op() -> Callable[[Any], Op2]: ...


@overload
def op(func: Any) -> Op2: ...


# def op(func: Optional[T] = None) -> Union[Callable[[T], Op2], Op2]:
def op(*args, **kwargs) -> Union[Callable[[Any], Op2], Op2]:
    """The op decorator!"""
    if context_state.get_loading_built_ins():
        from weave.legacy.decorator_op import op as legacy_op

        return legacy_op(*args, **kwargs)  # type: ignore

    def op_deco(func: T) -> Op2:
        # Check function type
        sig = inspect.signature(func)
        is_method = _is_method_alt(func)
        is_async = inspect.iscoroutinefunction(func)

        def create_wrapper(func):
            if is_async:

                @wraps(func)
                async def wrapper(*args, **kwargs):
                    if client_context.weave_client.get_weave_client() is None:
                        return await func(*args, **kwargs)
                    call = _create_call(wrapper, *args, **kwargs)
                    return await _execute_call(
                        wrapper, call, *args, return_type="normal", **kwargs
                    )
            else:

                @wraps(func)
                def wrapper(*args, **kwargs):
                    if client_context.weave_client.get_weave_client() is None:
                        return func(*args, **kwargs)

                    print(f"{wrapper._on_output_handler=}")

                    call = _create_call(wrapper, *args, **kwargs)
                    return _execute_call(
                        wrapper, call, *args, return_type="normal", **kwargs
                    )

            # Tack these helpers on to our wrapper
            # should this be qualname?
            wrapper.resolve_fn = func  # type: ignore
            wrapper.name = func.__qualname__ if is_method else func.__name__  # type: ignore
            wrapper.signature = sig  # type: ignore
            wrapper.ref = None  # type: ignore

            # f = MethodType(wrapper, wrapper) if is_method else wrapper
            wrapper.call = partial(call, wrapper)  # type: ignore
            wrapper.calls = partial(calls, wrapper)  # type: ignore

            wrapper.__call__ = wrapper  # type: ignore
            wrapper.__self__ = wrapper  # type: ignore

            wrapper._set_on_output_handler = partial(_set_on_output_handler, wrapper)  # type: ignore
            wrapper._on_output_handler = None  # type: ignore

            return cast(Op2, wrapper)

        return create_wrapper(func)

    # def op_deco(func: T) -> Op2:
    #     # We go through this process instead of using a class to make the decorated
    #     # funcs pass `inspect.isfunction` and `inspect.iscoroutinefunction` checks.

    #     # check function type
    #     sig = inspect.signature(func)
    #     params = list(sig.parameters.values())
    #     is_method = params and params[0].name in {"self", "cls"}
    #     is_async = inspect.iscoroutinefunction(func)

    #     def op_making_wrapper(func) -> Op2:
    #         @wraps(func)
    #         def wrapper(*args, **kwargs):
    #             return func(*args, **kwargs)

    #         # Tack these helpers on to our "class function"
    #         wrapper.name = func.__qualname__  # type: ignore
    #         wrapper.signature = sig  # type: ignore
    #         wrapper.ref = None  # type: ignore

    #         f = MethodType(wrapper, wrapper) if is_method else wrapper
    #         wrapper.call = partial(call, wrapper)  # type: ignore
    #         wrapper.calls = partial(calls, wrapper)  # type: ignore

    #         wrapper.__call__ = wrapper  # type: ignore
    #         wrapper.__self__ = wrapper  # type: ignore

    #         return cast(Op2, wrapper)

    #     made_op = op_making_wrapper(func)

    #     if is_async:

    #         @wraps(made_op)
    #         async def async_wrapper(*args, **kwargs):
    #             if client_context.weave_client.get_weave_client() is None:
    #                 return made_op(*args, **kwargs)
    #             call = _create_call(made_op, *args, **kwargs)
    #             return await _execute_call(
    #                 made_op, call, *args, return_type="normal", **kwargs
    #             )

    #         return async_wrapper
    #     else:

    #         @wraps(made_op)
    #         def sync_wrapper(*args, **kwargs):
    #             if client_context.weave_client.get_weave_client() is None:
    #                 return made_op(*args, **kwargs)
    #             call = _create_call(made_op, *args, **kwargs)
    #             return _execute_call(
    #                 made_op, call, *args, return_type="normal", **kwargs
    #             )

    #         return sync_wrapper

    #     return made_op

    #     # This is the equivalent of the old Op's __call__ method
    #     if is_async:

    #         @wraps(made_op)
    #         async def wrapper(*args: Any, **kwargs: Any) -> Any:
    #             if client_context.weave_client.get_weave_client() is None:
    #                 return await made_op(*args, **kwargs)
    #             call = _create_call(made_op, *args, **kwargs)  # type: ignore
    #             return await _execute_call(
    #                 made_op, call, *args, return_type="normal", **kwargs
    #             )

    #     else:

    #         @wraps(made_op)
    #         def wrapper(*args: Any, **kwargs: Any) -> Any:
    #             if client_context.weave_client.get_weave_client() is None:
    #                 return made_op(*args, **kwargs)
    #             call = _create_call(made_op, *args, **kwargs)  # type: ignore
    #             return _execute_call(
    #                 made_op, call, *args, return_type="normal", **kwargs
    #             )

    #     # there should be a better way than this...
    #     wrapper.name = func.name  # type: ignore
    #     wrapper.signature = func.signature  # type: ignore
    #     wrapper.ref = func.ref  # type: ignore
    #     wrapper.call = func.call  # type: ignore
    #     wrapper.calls = func.calls  # type: ignore
    #     wrapper.__call__ = wrapper  # type: ignore
    #     wrapper.__self__ = func  # type: ignore

    #     return cast(Op2, wrapper)

    # # if func is None:
    # #     return op_deco
    # # return op_deco(func)

    if len(args) == 1 and len(kwargs) == 0 and callable(func := args[0]):
        # return wrap(args[0])
        return op_deco(func)

    return op_deco
