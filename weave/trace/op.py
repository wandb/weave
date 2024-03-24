from typing import Callable, Any, Optional
import inspect
import functools
import typing
from typing import TYPE_CHECKING, TypeVar, Callable, Optional, Coroutine
from typing_extensions import ParamSpec

from weave.trace_server.refs import ObjectRef
from weave import graph_client_context
from weave import run_context
from weave import box

from weave import context_state

from weave.trace.op_type import OpType

if TYPE_CHECKING:
    from weave.weave_client import Call, WeaveClient, CallsIter


def print_call_link(call: "Call") -> None:
    print(f"🍩 {call.ui_url}")


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
        return BoundOp(obj, self)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        maybe_client = graph_client_context.get_graph_client()
        if maybe_client is None:
            return self.resolve_fn(*args, **kwargs)
        client = typing.cast("WeaveClient", maybe_client)

        inputs = self.signature.bind(*args, **kwargs).arguments
        parent_run = run_context.get_current_run()
        trackable_inputs = client.save_nested_objects(inputs)
        run = client.create_call(self, parent_run, trackable_inputs)
        try:
            with run_context.current_run(run):
                res = self.resolve_fn(**trackable_inputs)
                # TODO: can we get rid of this?
                res = box.box(res)
        except BaseException as e:
            client.fail_run(run, e)
            if not parent_run:
                print_call_link(run)
            raise
        if isinstance(res, box.BoxedNone):
            res = None
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
                    client.fail_run(run, e)
                    if not parent_run:
                        print_call_link(run)
                    raise

            return _run_async()
        else:
            client.finish_call(run, res)
            if not parent_run:
                print_call_link(run)

        return res

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

    def __init__(self, arg0: Any, op: Op) -> None:
        self.arg0 = arg0
        self.op = op
        self.name = arg0.__class__.__name__ + "." + op.resolve_fn.__name__
        self.signature = inspect.signature(op.resolve_fn)
        self.resolve_fn = op.resolve_fn

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.op(self.arg0, *args, **kwargs)

    @property
    def ref(self) -> Optional[ObjectRef]:
        return self.op.__ref

    @ref.setter
    def ref(self, ref: ObjectRef) -> None:
        self.op.__ref = ref


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
