import contextvars
import contextlib
import dataclasses
import functools
import uuid
import typing

from . import context_state
from . import uris
from . import weave_internal
from . import monitoring
from . import wandb_api
from . import artifact_wandb
from . import graph
from . import op_def
from . import stream_data_interfaces
from . import weave_types as types
from .eager import WeaveIter, select_all
from .run import Run


@dataclasses.dataclass
class GraphClient:
    entity_name: str
    project_name: str

    @property
    def entity_project(self) -> str:
        return f"{self.entity_name}/{self.project_name}"

    @functools.cached_property
    def runs_st(self) -> monitoring.StreamTable:
        return monitoring.StreamTable(f"{self.entity_name}/{self.project_name}/stream")

    @functools.cached_property
    def run_feedback_st(self) -> monitoring.StreamTable:
        return monitoring.StreamTable(
            f"{self.entity_name}/{self.project_name}/run-feedback"
        )

    def runs(self) -> WeaveIter[Run]:
        return WeaveIter(self.runs_st.rows(), cls=Run)

    def run(self, run_id: str) -> typing.Optional[Run]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(lambda row: row["span_id"] == run_id)[0]  # type: ignore
            run_attrs = weave_internal.use(select_all(filter_node))
            if not isinstance(run_attrs, dict):
                return None
            if run_attrs["span_id"] == None:
                return None
            run_attrs = typing.cast(stream_data_interfaces.TraceSpanDict, run_attrs)
            return Run(run_attrs)

    def run_children(self, run_id: str) -> WeaveIter[Run]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(lambda row: row["parent_id"] == run_id)  # type: ignore
            return WeaveIter(filter_node, cls=Run)

    # Hmm... I want this to be a ref to an op I think?
    def op_runs(self, op_def: op_def.OpDef) -> WeaveIter[Run]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(  # type: ignore
                lambda row: row["name"] == str(op_def.location)
            )
            return WeaveIter(filter_node, cls=Run)

    def ref_input_to(self, ref: artifact_wandb.WandbArtifactRef) -> WeaveIter[Run]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(lambda row: row["inputs._ref0"] == ref)  # type: ignore
            return WeaveIter(filter_node, cls=Run)

    def ref_value_input_to(
        self, ref: artifact_wandb.WandbArtifactRef
    ) -> WeaveIter[Run]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(lambda row: row["inputs._ref_digest0"] == ref.digest)  # type: ignore
            return WeaveIter(filter_node, cls=Run)

    def ref_output_of(
        self, ref: artifact_wandb.WandbArtifactRef
    ) -> typing.Optional[Run]:
        with context_state.lazy_execution():
            rows_node = self.runs_st.rows()
            filter_node = rows_node.filter(lambda row: row["outputs._ref0"] == ref)[0]  # type: ignore
            run_attrs = weave_internal.use(select_all(filter_node))
            if not isinstance(run_attrs, dict):
                return None
            if run_attrs["span_id"] == None:
                return None
            run_attrs = typing.cast(stream_data_interfaces.TraceSpanDict, run_attrs)
            return Run(run_attrs)

    def add_feedback(self, run_id: str, feedback: dict[str, typing.Any]) -> None:
        feedback_id = str(uuid.uuid4())
        self.run_feedback_st.log(
            {"run_id": run_id, "feedback_id": feedback_id, "feedback": feedback}
        )

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
