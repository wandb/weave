import collections
from types import AsyncGeneratorType, GeneratorType
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

        def finish_with_output(output: Any) -> None:
            client.finish_call(run, output)
            if not parent_run:
                print_call_link(run)

        def fail_with_error(error: BaseException) -> None:
            client.fail_call(run, error)
            if not parent_run:
                print_call_link(run)

        def fail_with_partial_output(output: Any, error: BaseException) -> None:
            client.finish_call(run, output, error)
            if not parent_run:
                print_call_link(run)

        try:
            with run_context.current_run(run):
                res = self.resolve_fn(*args, **kwargs)
                # TODO: can we get rid of this?
                res = box.box(res)
        except BaseException as e:
            fail_with_error(e)
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
                    with run_context.current_run(run):
                        output = await res
                except BaseException as e:
                    fail_with_error(e)
                    raise
                finish_with_output(output)
                return output

            return _run_async()
        elif inspect.isasyncgen(res):
            # We want to accumulate the iterations of the async generator
            # before finishing the call. The exit conditions are:
            # * The generator is exhausted
            # * The generator raises an exception
            # * The generator is GC'd (early break)
            # * The generator is closed (early break)
            class WeaveAsyncGenerator:
                def __init__(self, gen: AsyncGeneratorType) -> None:
                    self.gen = gen
                    self.iterations: list[Any] = []
                    self.finished = False

                def __aiter__(self) -> "WeaveAsyncGenerator":
                    return self

                async def __anext__(self) -> Any:
                    try:
                        with run_context.current_run(run):
                            next_val = await self.gen.__anext__()
                        self.iterations.append(next_val)
                        return next_val
                    except StopAsyncIteration as e:
                        self.finished = True
                        finish_with_output(self.iterations)
                        raise e
                    except BaseException as e:
                        self.finished = True
                        fail_with_partial_output(self.iterations, e)
                        raise e

                def close(self) -> None:
                    if not self.finished:
                        self.finished = True
                        finish_with_output(self.iterations)

                def __del__(self) -> None:
                    if not self.finished:
                        self.finished = True
                        finish_with_output(self.iterations)

            return WeaveAsyncGenerator(res)
        elif inspect.isgenerator(res):
            # We want to accumulate the iterations of the generator
            # before finishing the call. The exit conditions are:
            # * The generator is exhausted
            # * The generator raises an exception
            # * The generator is GC'd (early break)
            # * The generator is closed (early break)
            class WeaveGenerator:
                def __init__(self, gen: GeneratorType) -> None:
                    self.gen = gen
                    self.iterations: list[Any] = []
                    self.finished = False

                def __iter__(self) -> "WeaveGenerator":
                    return self

                def __next__(self) -> Any:
                    try:
                        with run_context.current_run(run):
                            next_val = next(self.gen)
                        self.iterations.append(next_val)
                        return next_val
                    except StopIteration as e:
                        self.finished = True
                        finish_with_output(self.iterations)
                        raise e
                    except BaseException as e:
                        self.finished = True
                        fail_with_partial_output(self.iterations, e)
                        raise e

                def close(self) -> None:
                    if not self.finished:
                        self.finished = True
                        finish_with_output(self.iterations)

                def __del__(self) -> None:
                    if not self.finished:
                        self.finished = True
                        finish_with_output(self.iterations)

            return WeaveGenerator(res)
        elif isinstance(res, collections.abc.Iterable) and not isinstance(
            res, (str, bytes, bytearray, memoryview, range, tuple, list, set, frozenset, dict)):
            print(res, type(res))
            # Ok, here we have to somehow wrap the iterable
            # so that we can accumulate the iterations before
            # finishing the call. The exit conditions are:
            # * The iterable is exhausted
            # * The iterable raises an exception
            # * The iterable is GC'd (early break)
            # * The iterable is closed (early break)
            # class WeaveIterable(type(res)):  # type: ignore
            class WeaveIterable():  # type: ignore
                def __init__(self, wrapped: collections.abc.Iterable) -> None:
                    self.iterable = wrapped
                    self.iterations: list[Any] = []
                    self.finished = False

                def __iter__(self) -> "WeaveIterable":
                    return self

                def __next__(self) -> Any:  # type: ignore
                    try:
                        next_val = next(self.iterable)  # type: ignore
                        self.iterations.append(next_val)
                        return next_val
                    except StopIteration as e:
                        self.finished = True
                        finish_with_output(self.iterations)
                        raise e
                    except BaseException as e:
                        self.finished = True
                        fail_with_partial_output(self.iterations, e)
                        raise e

                def close(self) -> None:
                    if not self.finished:
                        self.finished = True
                        finish_with_output(self.iterations)

                # def __del__(self) -> None:
                #     if not self.finished:
                #         self.finished = True
                #         finish_with_output(self.iterations)

                def __getattr__(self, name: str) -> Any:
                    if name == "close":
                        return self.__dict__['close']
                    # if name == "__del__":
                    #     return self.__dict__['__del__']
                    if name == "__iter__":
                        return self.__dict__['__iter__']
                    if name == "__next__":
                        return self.__dict__['__next__']
                    return getattr(self.iterable, name)

            return WeaveIterable(res)
        elif isinstance(res, collections.abc.AsyncIterable):  # type: ignore
            # Ok, here we have to somehow wrap the iterable
            # so that we can accumulate the iterations before
            # finishing the call. The exit conditions are:
            # * The iterable is exhausted
            # * The iterable raises an exception
            # * The iterable is GC'd (early break)
            # * The iterable is closed (early break)
            class WeaveAsyncIterable(type(res)):  # type: ignore
                def __init__(self, wrapped: collections.abc.AsyncIterable) -> None:
                    self.iterable = wrapped
                    self.iterations: list[Any] = []
                    self.finished = False

                def __aiter__(self) -> "WeaveAsyncIterable":
                    return self

                async def __anext__(self) -> Any:  # type: ignore
                    try:
                        next_val = await anext(self.iterable)  # type: ignore
                        self.iterations.append(next_val)
                        return next_val
                    except StopAsyncIteration as e:
                        self.finished = True
                        finish_with_output(self.iterations)
                        raise e
                    except BaseException as e:
                        self.finished = True
                        fail_with_partial_output(self.iterations, e)
                        raise e

                def close(self) -> None:
                    if not self.finished:
                        self.finished = True
                        finish_with_output(self.iterations)

                def __del__(self) -> None:
                    if not self.finished:
                        self.finished = True
                        finish_with_output(self.iterations)

                # def __getattr__(self, name: str) -> Any:
                #     return getattr(self.iterable, name)

            return WeaveAsyncIterable(res)
        else:
            finish_with_output(res)

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
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                inputs[param_name] = tuple()
            elif param.kind == inspect.Parameter.VAR_KEYWORD:
                inputs[param_name] = dict()
    return inputs
