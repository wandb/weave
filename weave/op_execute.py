import typing
from typing import Mapping
import inspect

from weave.weave_client import Call

from . import graph_client_context
from . import context_state
from . import run_context
from . import object_context
from . import storage
from . import ref_base
from . import weave_types as types
from . import box

if typing.TYPE_CHECKING:
    from .op_def import OpDef


def print_run_link(run):
    print(f"🍩 {run.ui_url}")


def execute_op(op_def: "OpDef", inputs: Mapping[str, typing.Any]):
    client = graph_client_context.get_graph_client()
    if client is not None and context_state.eager_mode():
        parent_run = run_context.get_current_run()
        trackable_inputs = client.save_nested_objects(inputs)

        # Memoization disabled for now.
        # found_run = client.find_op_run(str(op_def_ref), mon_span_inputs)
        # if found_run:
        #     return found_run.output
        if not isinstance(parent_run, Call):
            raise ValueError("parent_run must be a Call")

        run = client.create_call(op_def, parent_run, trackable_inputs)
        try:
            with run_context.current_run(run):
                res = op_def.raw_resolve_fn(**trackable_inputs)
                res = box.box(res)
        except BaseException as e:
            client.fail_run(run, e)
            if not parent_run:
                print_run_link(run)
            raise
        if isinstance(res, box.BoxedNone):
            res = None

        # Don't use asyncio.iscoroutine. It returns True for non-async
        # generators sometimes. Use inspect.iscoroutine instead.
        if inspect.iscoroutine(res):

            async def _run_async():
                try:
                    awaited_res = res
                    with object_context.object_context():
                        with run_context.current_run(run):
                            # Need to do this in a loop for some reason to handle
                            # async streaming openai. Like we get two co-routines
                            # in a row.
                            while inspect.iscoroutine(awaited_res):
                                awaited_res = await awaited_res
                    # output, output_refs = auto_publish(awaited_res)
                    output, output_refs = awaited_res, []
                    # TODO: boxing enables full ref-tracking of run outputs
                    # to other run inputs, but its not working yet.
                    # output = box.box(output)
                    client.finish_call(run, output)
                    if not parent_run:
                        print_run_link(run)
                    return output
                    # return _deref_all(output)
                except BaseException as e:
                    client.fail_run(run, e)
                    if not parent_run:
                        print_run_link(run)
                    raise

            return _run_async()
        else:
            client.finish_call(run, res)
            if not parent_run:
                print_run_link(run)

    else:
        res = op_def.resolve_fn(**inputs)

    return res
