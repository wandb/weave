import copy
import dataclasses
import functools
import hashlib
import uuid
import time
import json
import typing
from typing import Sequence

from collections.abc import Mapping
from .graph_client import GraphClient
from . import urls
from . import context_state
from . import weave_internal
from . import monitoring
from .monitoring import monitor
from . import artifact_wandb
from . import op_def
from .ref_base import Ref
from . import stream_data_interfaces
from .eager import WeaveIter, select_all
from .run import RunKey, Run
from .run_streamtable_span import RunStreamTableSpan
from . import stream_data_interfaces


def refs_to_str(val: typing.Any) -> typing.Any:
    if isinstance(val, Ref):
        return str(val)
    elif isinstance(val, dict):
        return {k: refs_to_str(v) for k, v in val.items()}  # type: ignore
    elif isinstance(val, list):
        return [refs_to_str(v) for v in val]  # type: ignore
    else:
        return val


def hash_inputs(
    inputs: Mapping[str, typing.Any],
) -> str:
    hasher = hashlib.md5()
    hasher.update(json.dumps(refs_to_str(inputs)).encode())
    return hasher.hexdigest()


class GraphClientWandbArtStreamTable(GraphClient[RunStreamTableSpan]):
    entity_name: str
    project_name: str

    def __init__(self, entity_name: str, project_name: str):
        self.entity_name = entity_name
        self.project_name = project_name

    @functools.cached_property
    def runs_st(self) -> monitoring.StreamTable:
        return monitoring.StreamTable(f"{self.entity_name}/{self.project_name}/stream")

    @functools.cached_property
    def run_feedback_st(self) -> monitoring.StreamTable:
        return monitoring.StreamTable(
            f"{self.entity_name}/{self.project_name}/run-feedback"
        )

    ##### Read API

    def runs(self) -> WeaveIter[RunStreamTableSpan]:
        return WeaveIter(self.runs_st.rows(), cls=RunStreamTableSpan)

    def run(self, run_id: str) -> typing.Optional[RunStreamTableSpan]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(lambda row: row["span_id"] == run_id)[0]  # type: ignore
            run_attrs = weave_internal.use(select_all(filter_node))
            if not isinstance(run_attrs, dict):
                return None
            if run_attrs["span_id"] == None:
                return None
            run_attrs = typing.cast(stream_data_interfaces.TraceSpanDict, run_attrs)
            return RunStreamTableSpan(run_attrs)

    def find_op_run(
        self, op_name: str, inputs: dict[str, typing.Any]
    ) -> typing.Optional[RunStreamTableSpan]:
        from . import ops_primitives

        inputs_digest = hash_inputs(inputs)
        from . import compile

        with context_state.lazy_execution():
            with compile.enable_compile():
                rows_node = self.runs_st.rows()
                filter_node = rows_node.filter(  # type: ignore
                    lambda row: ops_primitives.Boolean.bool_and(
                        row["name"] == op_name,
                        row["attributes"]["_inputs_digest"] == inputs_digest,
                    )
                )[
                    0
                ]  # type: ignore
                run_attrs = weave_internal.use(select_all(filter_node))
                if not isinstance(run_attrs, dict):
                    return None
                if run_attrs.get("span_id") == None:
                    return None
                run_attrs = typing.cast(stream_data_interfaces.TraceSpanDict, run_attrs)
                return RunStreamTableSpan(run_attrs)

    def run_children(self, run_id: str) -> WeaveIter[RunStreamTableSpan]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(lambda row: row["parent_id"] == run_id)  # type: ignore
            return WeaveIter(filter_node, cls=RunStreamTableSpan)

    # Hmm... I want this to be a ref to an op I think?
    def op_runs(self, op_def: op_def.OpDef) -> WeaveIter[RunStreamTableSpan]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(  # type: ignore
                lambda row: row["name"] == str(op_def.location)
            )
            return WeaveIter(filter_node, cls=RunStreamTableSpan)

    def ref_input_to(self, ref: Ref) -> WeaveIter[RunStreamTableSpan]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(lambda row: row["inputs._ref0"] == ref)  # type: ignore
            return WeaveIter(filter_node, cls=RunStreamTableSpan)

    def ref_value_input_to(self, ref: Ref) -> WeaveIter[RunStreamTableSpan]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(lambda row: row["inputs._ref_digest0"] == ref.digest)  # type: ignore
            return WeaveIter(filter_node, cls=RunStreamTableSpan)

    def ref_output_of(self, ref: Ref) -> typing.Optional[RunStreamTableSpan]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(lambda row: row["outputs._ref0"] == ref)[0]  # type: ignore
            run_attrs = weave_internal.use(select_all(filter_node))
            if not isinstance(run_attrs, dict):
                return None
            if run_attrs["span_id"] == None:
                return None
            run_attrs = typing.cast(stream_data_interfaces.TraceSpanDict, run_attrs)
            return RunStreamTableSpan(run_attrs)

    def run_feedback(self, run_id: str) -> WeaveIter[dict[str, typing.Any]]:
        with context_state.lazy_execution():
            rows_node = self.run_feedback_st.rows()
            filter_node = rows_node.filter(lambda row: row["run_id"] == run_id)  # type: ignore
            return WeaveIter(filter_node)

    def feedback(self, feedback_id: str) -> typing.Optional[dict[str, typing.Any]]:
        with context_state.lazy_execution():
            rows_node = self.run_feedback_st.rows()
            filter_node = rows_node.filter(lambda row: row["feedback_id"] == feedback_id)[0]  # type: ignore
            feedback_attrs = weave_internal.use(select_all(filter_node))
            if not isinstance(feedback_attrs, dict):
                return None
            if feedback_attrs["feedback_id"] == None:
                return None
            return feedback_attrs

    # Helpers

    def ref_is_own(self, ref: typing.Optional[Ref]) -> bool:
        return isinstance(ref, artifact_wandb.WandbArtifactRef)

    def ref_uri(
        self, name: str, version: str, path: str
    ) -> artifact_wandb.WeaveWBArtifactURI:
        return artifact_wandb.WeaveWBArtifactURI(
            name, version, self.entity_name, self.project_name, path=path
        )

    def run_ui_url(self, run: Run) -> str:
        return urls.call_path_as_peek(
            self.entity_name,
            self.project_name,
            run.id,
        )

    ##### Write API

    def save_object(
        self, obj: typing.Any, name: str, branch_name: str
    ) -> artifact_wandb.WandbArtifactRef:
        from . import storage

        res = storage._direct_publish(
            obj,
            name=name,
            wb_entity_name=self.entity_name,
            wb_project_name=self.project_name,
            branch_name=branch_name,
        )
        return res

    def create_run(
        self,
        op_name: str,
        parent: typing.Optional["RunKey"],
        inputs: typing.Dict[str, typing.Any],
        input_refs: Sequence[Ref],
    ) -> RunStreamTableSpan:
        inputs_digest = hash_inputs(inputs)
        attrs = {"_inputs_digest": inputs_digest}
        inputs = copy.copy(inputs)
        inputs["_keys"] = list(inputs.keys())
        for i, ref in enumerate(input_refs[:3]):
            inputs["_ref%s" % i] = ref
            inputs["_ref_digest%s" % i] = ref.digest

        if parent:
            trace_id = parent.trace_id
            parent_id = parent.id
        else:
            trace_id = str(uuid.uuid4())
            parent_id = None
        cur_time = time.time()
        span = stream_data_interfaces.TraceSpanDict(
            span_id=str(uuid.uuid4()),
            trace_id=trace_id,
            parent_id=parent_id,
            name=op_name,
            status_code="UNSET",
            start_time_s=cur_time,
            end_time_s=cur_time,  # currently required, so set to start time for now?
            inputs=inputs,
            attributes=attrs,
            output=None,
            summary=None,
            exception=None,
        )
        # Don't log create for now
        # self.runs_st.log(span)
        return RunStreamTableSpan(span)

    def fail_run(self, run: RunStreamTableSpan, exception: BaseException) -> None:
        span = copy.copy(run._attrs)
        span["end_time_s"] = time.time()
        span["status_code"] = "ERROR"
        span["exception"] = str(exception)
        span["summary"] = {"latency_s": span["end_time_s"] - span["start_time_s"]}
        self.runs_st.log(span)

    def finish_run(
        self,
        run: RunStreamTableSpan,
        output: typing.Any,
        output_refs: Sequence[Ref],
    ) -> None:
        span = copy.copy(run._attrs)
        output = copy.copy(output)
        if not isinstance(output, dict):
            output = {"_result": output}
        output["_keys"] = list(output.keys())
        for i, ref in enumerate(output_refs[:3]):
            output["_ref%s" % i] = ref
            output["_ref_digest%s" % i] = ref.digest
        span["end_time_s"] = time.time()
        span["status_code"] = "SUCCESS"
        span["output"] = output
        span["summary"] = {"latency_s": span["end_time_s"] - span["start_time_s"]}
        span["attributes"] = monitor._attributes.get()

        self.runs_st.log(span)

    def add_feedback(self, run_id: str, feedback: dict[str, typing.Any]) -> None:
        feedback_id = str(uuid.uuid4())
        self.run_feedback_st.log(
            {"run_id": run_id, "feedback_id": feedback_id, "feedback": feedback}
        )
