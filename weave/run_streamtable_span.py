import typing
from typing import Iterable

from .run import Run
from . import uris
from . import artifact_wandb
from . import stream_data_interfaces
from . import graph_client_context
from .eager import WeaveIter


class RunStreamTableSpan:
    _attrs: stream_data_interfaces.TraceSpanDict

    def __init__(self, attrs: stream_data_interfaces.TraceSpanDict) -> None:
        self._attrs = attrs

    def __repr__(self) -> str:
        return f"<Run {self.uri} {self.id}>"

    @property
    def id(self) -> str:
        return self._attrs["span_id"]

    @property
    def trace_id(self) -> str:
        return self._attrs["trace_id"]

    @property
    def uri(self) -> str:
        return self._attrs["name"]

    @property
    def ui_url(self) -> str:
        gc = graph_client_context.require_graph_client()
        return gc.run_ui_url(self)

    @property
    def op_ref(self) -> typing.Optional[artifact_wandb.WandbArtifactRef]:
        if self.uri.startswith("wandb-artifact"):
            parsed = uris.WeaveURI.parse(self.uri).to_ref()
            if not isinstance(parsed, artifact_wandb.WandbArtifactRef):
                raise ValueError("expected wandb artifact ref")
            return parsed
        return None

    @property
    def status_code(self) -> str:
        return self._attrs["status_code"]

    @property
    def attributes(self) -> dict[str, typing.Any]:
        attrs_dict = self._attrs.get("attributes", {})
        if not isinstance(attrs_dict, dict):
            return {}
        return {k: v for k, v in attrs_dict.items() if v != None}

    @property
    def inputs(self) -> dict[str, typing.Any]:
        input_dict = self._attrs.get("input", {})
        if not isinstance(input_dict, dict):
            return {}
        keys = input_dict.get("_keys")
        if keys is None:
            keys = [k for k in input_dict.keys() if input_dict[k] != None]
        return {k: input_dict[k] for k in keys}

    @property
    def output(self) -> typing.Any:
        if self.status_code != "SUCCESS":
            return None
        out = self._attrs.get("output")
        if isinstance(out, dict):
            keys = out.get("_keys")
            if keys is None:
                keys = [k for k in out.keys() if out[k] != None]
            output = {k: out.get(k) for k in keys}
            if "_result" in output:
                return output["_result"]
        return out

    @property
    def parent_id(self) -> typing.Optional[str]:
        return self._attrs["parent_id"]

    def add_feedback(self, feedback: dict[str, typing.Any]) -> None:
        client = graph_client_context.require_graph_client()
        client.add_feedback(self.id, feedback)

    def feedback(self) -> Iterable[dict[str, typing.Any]]:
        client = graph_client_context.require_graph_client()
        return client.run_feedback(self.id)

    def parent(self) -> typing.Optional["Run"]:
        client = graph_client_context.require_graph_client()
        if self.parent_id is None:
            return None
        return client.run(self.parent_id)
