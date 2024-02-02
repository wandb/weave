import typing
from typing import Mapping
import inspect

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


def _deref_all(obj: typing.Any):
    if isinstance(obj, dict):
        return {k: _deref_all(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deref_all(v) for v in obj]
    elif isinstance(obj, ref_base.Ref):
        return obj.get()
    return obj


def _auto_publish(obj: typing.Any, output_refs: typing.List[ref_base.Ref]):
    import numpy as np

    ref = storage.get_ref(obj)
    if ref:
        output_refs.append(ref)
        return ref

    if isinstance(obj, dict):
        return {k: _auto_publish(v, output_refs) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_auto_publish(v, output_refs) for v in obj]
    weave_type = types.TypeRegistry.type_of(obj)
    if weave_type == types.UnknownType():
        return f"<UnknownType: {type(obj)}>"
    if not (
        types.is_custom_type(weave_type) or isinstance(weave_type, types.ObjectType)
    ):
        return obj

    client = graph_client_context.require_graph_client()
    if not ref:
        ref = client.save_object(obj, f"{obj.__class__.__name__}", "latest")

    output_refs.append(ref)
    return ref


def auto_publish(obj: typing.Any) -> typing.Tuple[typing.Any, list]:
    refs: typing.List[ref_base.Ref] = []
    return _auto_publish(obj, refs), refs


def execute_op(op_def: "OpDef", inputs: Mapping[str, typing.Any]):
    mon_span_inputs = {**inputs}
    client = graph_client_context.get_graph_client()
    if client is not None and context_state.eager_mode() and op_def.location:
        op_def_ref = storage._get_ref(op_def)
        if not client.ref_is_own(op_def_ref):
            op_def_ref = client.save_object(op_def, f"{op_def.name}", "latest")
        mon_span_inputs, refs = auto_publish(inputs)

        # Memoization disabled for now.
        # found_run = client.find_op_run(str(op_def_ref), mon_span_inputs)
        # if found_run:
        #     return found_run.output

        parent_run = run_context.get_current_run()
        # if not parent_run:
        #     print("Running ", op_def.name)
        run = client.create_run(str(op_def_ref), parent_run, mon_span_inputs, refs)
        try:
            with run_context.current_run(run):
                res = op_def.resolve_fn(**inputs)
        except BaseException as e:
            print("Error running ", op_def.name)
            client.fail_run(run, e)
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
                    output, output_refs = auto_publish(awaited_res)
                    # TODO: boxing enables full ref-tracking of run outputs
                    # to other run inputs, but its not working yet.
                    # output = box.box(output)
                    client.finish_run(run, output, output_refs)
                    if not parent_run:
                        print("🍩 View call:", run.ui_url)
                    return _deref_all(output)
                except Exception as e:
                    client.fail_run(run, e)
                    raise

            return _run_async()
        else:
            output, output_refs = auto_publish(res)
            # TODO: boxing enables full ref-tracking of run outputs
            # to other run inputs, but its not working yet.
            # output = box.box(output)

            client.finish_run(run, output, output_refs)
            if not parent_run:
                print("🍩 View call:", run.ui_url)
            res = _deref_all(output)

    else:
        res = op_def.resolve_fn(**inputs)

    return res
