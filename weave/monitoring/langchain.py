import datetime
import hashlib
import json
import typing

import wandb
from wandb.sdk.data_types import trace_tree

from weave.monitoring import StreamTable
from weave import stream_data_interfaces

# We should move this logic into our built-in langchain integration
from langchain.callbacks.tracers.base import BaseTracer
from langchain.callbacks.tracers.schemas import Run
from langchain.callbacks.tracers import wandb as LCW


def _hash_id(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()[:16]


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
            "id": _hash_id(model_str),
            "obj": model_str,
        }
        spans = stream_data_interfaces.wb_span_to_weave_spans(root_span)
        for span in spans:
            self._st.log(span)
