import datetime
import hashlib
import json
import typing

import wandb
from wandb.sdk.data_types import trace_tree
from weave.graph_client import GraphClient

from weave.monitoring import StreamTable
from weave import stream_data_interfaces
from weave import graph_client_context as _graph_client_context
from weave import op_def
from weave import weave_types

# We should move this logic into our built-in langchain integration
from langchain.callbacks.tracers.base import BaseTracer
from langchain.callbacks.tracers.schemas import Run
from langchain.callbacks.tracers import wandb as LCW


def _hash_id(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:16]


patched = False


# This should be committed to the langchain repo
# def patch_serialize() -> None:
#     global patched
#     if patched:
#         return
#     patched = True

#     old_serialize_io = LCW._serialize_io

#     def new_serialize_io(run_inputs):  # type: ignore
#         if run_inputs is None:
#             return {}
#         return old_serialize_io(run_inputs)

#     LCW._serialize_io = new_serialize_io


# patch_serialize()


class WeaveTracer(BaseTracer):
    def __init__(self, stream_uri: str, **kwargs: typing.Any) -> None:
        super().__init__(**kwargs)
        self.run_processor = LCW.RunProcessor(wandb, trace_tree)
        self._st = StreamTable(stream_uri)

    def _persist_run(self, run: Run) -> None:
        root_span = self.run_processor.process_span(run)
        if root_span is None:
            return
        model_dict = self.run_processor.process_model(run)
        model_str = json.dumps(model_dict)
        root_span.attributes["model"] = {
            # This is hardly an "id", since it is unique for each run.
            # Need to reconcile this with LC
            "id": _hash_id(model_str),
            "obj": model_str,
        }
        spans = stream_data_interfaces.wb_span_to_weave_spans(root_span)
        for span in spans:
            self._st.log(span)


from weave.run_streamtable_span import RunStreamTableSpan


def lc_run_to_weave_spans(
    run: Run, client: GraphClient
) -> typing.List[stream_data_interfaces.TraceSpanDict]:
    current_run_dict = run.dict()
    return lc_run_dict_to_weave_spans(current_run_dict, client)


def lc_run_dict_to_weave_spans(
    run: dict, client: GraphClient
) -> typing.List[stream_data_interfaces.TraceSpanDict]:
    spans = []
    try:
        span = lc_run_dict_to_weave_span(run, client)
        spans = [span]
    except Exception as e:
        print(e)
        return []
    for child_run_dict in run.get("child_runs", []):
        spans += lc_run_dict_to_weave_spans(child_run_dict, client)
    return spans


def lc_run_dict_to_weave_span(
    run: dict, client: GraphClient
) -> stream_data_interfaces.TraceSpanDict:
    dummy_dict = {"_": ""}
    attributes = {}

    parent_id = run.get("parent_run_id")
    if parent_id != None:
        parent_id = str(parent_id)

    tags = run.get("tags", [])
    if len(tags) != 0:
        attributes["tags"] = tags

    if len(attributes.keys()) == 0:
        attributes = dummy_dict

    ref = lc_serialized_to_refs(run["serialized"], client)

    op_def_ref = str(run["name"]) + "-run"
    # This is def not going to work in all cases
    try:

        def build_resolver(rn, lc, cid):
            def resolver(*args, **kwargs):
                name = rn
                langchain_version = lc
                component_id = cid

            return resolver

        resolver = build_resolver(
            op_def_ref,
            run["serialized"].get("lc", 1),
            str(run["serialized"].get("lc", [])),
        )
        dynamic_op_def = op_def.OpDef(
            str(run["name"]) + "-run",
            {},
            # op_args.OpNamedArgs(input_type),
            weave_types.NoneType(),
            # output_type,
            resolver,
            # resolve,
            # _mapped_refine_output_type(orig_op),
        )
        op_def_ref = client.save_object(dynamic_op_def, dynamic_op_def.name, "latest")
    except Exception as e:
        print(e)
        pass

    return stream_data_interfaces.TraceSpanDict(
        span_id=str(run["id"]),
        # The name of the span - typically the name of the operation
        name=str(op_def_ref),
        # name = str(run['name']) + "-run",
        # The ID of the trace this span belongs to - typically a UUID
        trace_id=str(run["trace_id"]),
        # The status code conforming to the OpenTelemetry spec
        # Options: "SUCCESS", "ERROR", "UNSET"
        status_code="SUCCESS" if run["error"] == None else "ERROR",
        # Start and end times in seconds since the epoch
        start_time_s=run["start_time"].timestamp(),
        end_time_s=run["start_time"].timestamp(),
        # The parent span ID - typically a UUID (optional)
        # if not set, this is a root span
        parent_id=parent_id,
        # **Weave specific keys**
        # Attributes are any key value pairs associated with the span,
        # typically known before the execution operation
        attributes=attributes,
        # Inputs are the parameters to the operation
        inputs={"self": ref, **run["inputs"]},
        # Output is the result of the operation
        output=run["outputs"],
        # Summary is a dictionary of key value pairs that summarize
        # the execution of the operation. This data is typically only
        # available after the operation has completed, as a function
        # of the output.
        summary={
            "latency_s": run["start_time"].timestamp() - run["start_time"].timestamp(),
        },
        # Exception is any free form string describing an exception
        # that occurred during the execution of the operation
        exception=run["error"],
    )


def lc_serialized_to_refs(
    serialized: dict, client: GraphClient
) -> typing.List[stream_data_interfaces.TraceSpanDict]:
    def dict_is_serialized_dict(d: dict) -> bool:
        return "type" in d and "lc" in d and "id" in d

    def sanitize_serialized_item(d: typing.Any) -> typing.Any:
        if isinstance(d, dict):
            res = {}
            for k, v in d.items():
                if k in ["type", "repr", "lc", "id"]:
                    continue
                if isinstance(v, dict):
                    if dict_is_serialized_dict(v):
                        serialized = sanitize_serialized_item(v)
                        if serialized is None:
                            continue
                        res[k] = sanitize_serialized_item(v)
                    else:
                        inner = {}
                        for inner_k, inner_v in v.items():
                            serialized = sanitize_serialized_item(inner_v)
                            if serialized is None:
                                continue
                            inner[inner_k] = serialized
                        if len(inner.keys()) == 0:
                            continue
                        res[k] = inner
                else:
                    res[k] = v
            if (
                dict_is_serialized_dict(d)
                and len(res.keys()) > 0
                and d["type"] != "secret"
            ):
                res = client.save_object(res, d["id"][-1], "latest")
            elif len(res.keys()) == 0 and len(d.keys()) > 0:
                return None
            return res
        elif isinstance(d, list):
            res = []
            for item in d:
                serialized = sanitize_serialized_item(item)
                if serialized is None:
                    continue
                res.append(serialized)
            if len(res) == 0:
                return None
            return res
        else:
            return d

    return sanitize_serialized_item(serialized)


class WeaveflowTracer(BaseTracer):
    def __init__(self, **kwargs: typing.Any) -> None:
        super().__init__(**kwargs)
        self.run_processor = LCW.RunProcessor(wandb, trace_tree)

    def _persist_run(self, run: Run) -> None:
        client = _graph_client_context.get_graph_client()
        if not client:
            raise ValueError("Call weave.init() first")
        spans = lc_run_to_weave_spans(run, client)
        for span in spans:
            if span["status_code"] == "ERROR":
                client.fail_run(
                    run=RunStreamTableSpan(span),
                    exception=Exception(span["exception"]),
                )
            else:
                client.finish_run(
                    run=RunStreamTableSpan(span),
                    output=span["output"],
                    output_refs=[],
                )
