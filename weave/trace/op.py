from typing import Callable, Any, Mapping, Optional
import inspect
import functools
import typing
from typing import TYPE_CHECKING, TypeVar, Callable, Optional, Coroutine
from typing_extensions import ParamSpec

from weave.trace.errors import OpCallError
from weave.trace.refs import ObjectRef
from weave.trace.context import call_attributes
from weave import graph_client_context
from weave import run_context
from weave import box

from weave import context_state

from weave.trace.op_type import OpType
from .constants import TRACE_CALL_EMOJI

if TYPE_CHECKING:
    from weave.weave_client import Call, WeaveClient, CallsIter


def print_call_link(call: "Call") -> None:
    print(f"{TRACE_CALL_EMOJI} {call.ui_url}")


class Op:
    resolve_fn: Callable
    # double-underscore to avoid conflict with old Weave refs
    __ref: Optional[ObjectRef] = None

    def __init__(self, resolve_fn: Callable) -> None:
        self.resolve_fn = resolve_fn
        self.name = resolve_fn.__name__
        self.signature = inspect.signature(resolve_fn)

    def __get__(
        self, obj: Optional[object], objtype: Optional[type[object]] = None
    ) -> "BoundOp":
        return BoundOp(obj, objtype, self)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._watched_call(*args, **kwargs)

    def _watched_call(self, *args: Any, **kwargs: Any) -> Any:
        maybe_client = graph_client_context.get_graph_client()
        if maybe_client is None:
            return self.resolve_fn(*args, **kwargs)
        client = typing.cast("WeaveClient", maybe_client)

        try:
            inputs = self.signature.bind(*args, **kwargs).arguments
        except TypeError as e:
            raise OpCallError(f"Error calling {self.name}: {e}")
        inputs_with_defaults = _apply_fn_defaults_to_inputs(self.resolve_fn, inputs)
        parent_run = run_context.get_current_run()
        client.save_nested_objects(inputs_with_defaults)
        attributes = call_attributes.get()
        run = client.create_call(
            self, parent_run, inputs_with_defaults, attributes=attributes
        )
        try:
            with run_context.current_run(run):
                res = self.resolve_fn(**inputs)
                # TODO: can we get rid of this?
                res = box.box(res)
        except BaseException as e:
            client.fail_call(run, e)
            if not parent_run:
                print_call_link(run)
            raise
        # We cannot let BoxedNone or BoxedBool escape into the user's code
        # since they cannot pass instance checks for None or bool.
        if isinstance(res, box.BoxedNone):
            res = None
        if isinstance(res, box.BoxedBool):
            res = res.val
        if inspect.iscoroutine(res):

            async def _run_async() -> Coroutine[Any, Any, Any]:
                try:
                    awaited_res = res
                    with run_context.current_run(run):
                        output = await awaited_res
                    client.finish_call(run, output)
                    if not parent_run:
                        print_call_link(run)
                    return output
                except BaseException as e:
                    client.fail_call(run, e)
                    if not parent_run:
                        print_call_link(run)
                    raise

            return _run_async()
        else:
            client.finish_call(run, res)
            if not parent_run:
                print_call_link(run)

        return res

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"

    @property
    def ref(self) -> Optional[ObjectRef]:
        return self.__ref

    @ref.setter
    def ref(self, ref: ObjectRef) -> None:
        self.__ref = ref

    def calls(self) -> "CallsIter":
        client = graph_client_context.require_graph_client()
        return client.op_calls(self)


OpType.instance_classes = Op


class BoundOp(Op):
    arg0: Any
    op: Op

    def __init__(
        self, arg0: object, arg0_class: Optional[type[object]], op: Op
    ) -> None:
        self.arg0 = arg0
        self.op = op  # type: ignore
        if arg0_class is None:
            self.name = op.resolve_fn.__name__
        else:
            self.name = arg0_class.__name__ + "." + op.resolve_fn.__name__
        self.signature = inspect.signature(op.resolve_fn)
        self.resolve_fn = op.resolve_fn

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
        from weave.decorator_op import op

        return op(*args, **kwargs)

    def wrap(f: Callable[P, R]) -> Callable[P, R]:
        op = Op(f)
        functools.update_wrapper(op, f)
        return op  # type: ignore

    return wrap


def _apply_fn_defaults_to_inputs(
    fn: typing.Callable, inputs: Mapping[str, typing.Any]
) -> dict[str, typing.Any]:
    inputs = {**inputs}
    sig = inspect.signature(fn)
    for param_name, param in sig.parameters.items():
        if param_name not in inputs:
            if param.default != inspect.Parameter.empty:
                inputs[param_name] = param.default
    return inputs
