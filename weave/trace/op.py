import functools
import inspect
import typing
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Coroutine,
    Dict,
    Mapping,
    Optional,
    TypeVar,
)

from typing_extensions import ParamSpec

from weave import call_context, client_context
from weave.legacy import box, context_state
from weave.trace.context import call_attributes
from weave.trace.errors import OpCallError
from weave.trace.refs import ObjectRef

from .constants import TRACE_CALL_EMOJI

if TYPE_CHECKING:
    from weave.weave_client import Call, CallsIter

try:
    from openai._types import NOT_GIVEN as OPENAI_NOT_GIVEN
except ImportError:
    OPENAI_NOT_GIVEN = None

try:
    from anthropic._types import NOT_GIVEN as ANTHROPIC_NOT_GIVEN
except ImportError:
    ANTHROPIC_NOT_GIVEN = None


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

        try:
            inputs = self.signature.bind(*args, **kwargs).arguments
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

    async def call(self, *args: Any, **kwargs: Any) -> "Call":
        _call = self._create_call(*args, **kwargs)
        await self._execute_call(_call, *args, **kwargs)
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
def op(*args: Any, **kwargs: Any) -> Callable[[Callable[P, R]], Callable[P, R]]:
    if context_state.get_loading_built_ins():
        from weave.legacy.decorator_op import op

        return op(*args, **kwargs)

    def wrap(f: Callable[P, R]) -> Callable[P, R]:
        op = Op(f)
        functools.update_wrapper(op, f)
        return op  # type: ignore

    if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
        return wrap(args[0])

    return wrap


def value_is_sentinel(param: Any) -> bool:
    return (
        param.default is None
        or param.default is OPENAI_NOT_GIVEN
        or param.default is ANTHROPIC_NOT_GIVEN
    )


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
