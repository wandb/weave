import datetime
import hashlib
import json
import typing

import wandb
from wandb.sdk.data_types import trace_tree

import weave
from weave.monitoring import StreamTable

# We should move this logic into our built-in langchain integration
from langchain.callbacks.tracers.base import BaseTracer
from langchain.callbacks.tracers.schemas import Run
from langchain.callbacks.tracers import wandb as LCW
from wandb.sdk.data_types.trace_tree import Span as WBSpan

from uuid import uuid4


# We rely on all the hard work already in our W&B integration and just
# simply map the properties of the WB Span to the Weave Span
def wb_span_to_weave_spans(
    wb_span: WBSpan,
    trace_id: typing.Optional[str] = None,
    parent_id: typing.Optional[str] = None,
) -> typing.List[weave.stream_data_interfaces.TraceSpanDict]:
    attributes = {**wb_span.attributes} if wb_span.attributes is not None else {}
    if hasattr(wb_span, "span_kind") and wb_span.span_kind is not None:
        attributes["span_kind"] = str(wb_span.span_kind)
    inputs = (
        wb_span.results[0].inputs
        if wb_span.results is not None and len(wb_span.results) > 0
        else None
    )
    outputs = (
        wb_span.results[0].outputs
        if wb_span.results is not None and len(wb_span.results) > 0
        else None
    )

    # Super Hack - fix merge!
    dummy_dict = {"_": ""} if parent_id == None else {}

    if (
        wb_span.start_time_ms is None
        or wb_span.end_time_ms is None
        or wb_span.span_id is None
        or wb_span.name is None
    ):
        return []

    span = weave.stream_data_interfaces.TraceSpanDict(
        start_time_s=wb_span.start_time_ms / 1000.0,
        end_time_s=wb_span.end_time_ms / 1000.0,
        span_id=wb_span.span_id,
        name=wb_span.name,
        status_code=str(wb_span.status_code),
        trace_id=trace_id or str(uuid4()),
        parent_id=parent_id,
        # Followup: allow None in attributes & summary (there is an issue with vectorized opMerge)
        # This should be fixed before integrating inside LC
        attributes=attributes or dummy_dict,
        summary=dummy_dict,
        inputs=inputs,
        output=outputs,
        exception=wb_span.status_message
        if wb_span.status_message is not None
        else None,
    )
    spans = [span]
    for child in wb_span.child_spans or []:
        spans += wb_span_to_weave_spans(child, span["trace_id"], span["span_id"])

    return spans


def _hash_id(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:16]


patched = False


# This should be committed to the langchain repo
def patch_serialize():
    global patched
    if patched:
        return
    patched = True

    old_serialize_io = LCW._serialize_io

    def new_serialize_io(run_inputs):
        if run_inputs is None:
            return {}
        return old_serialize_io(run_inputs)

    LCW._serialize_io = new_serialize_io


patch_serialize()


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
        spans = wb_span_to_weave_spans(root_span)
        for span in spans:
            self._st.log(span)
