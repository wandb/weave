import typing

from . import uris
from . import artifact_wandb
from . import stream_data_interfaces
from . import graph_client_context
from .eager import WeaveIter


class Run:
    _attrs: stream_data_interfaces.TraceSpanDict

    def __init__(self, attrs: stream_data_interfaces.TraceSpanDict) -> None:
        self._attrs = attrs

    def __repr__(self) -> str:
        return f"<Run {self.uri} {self.id}>"

    @property
    def id(self) -> str:
        return self._attrs["span_id"]

    @property
    def uri(self) -> str:
        return self._attrs["name"]

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
        return {k: v for k, v in self._attrs.get("attributes", {}).items() if v != None}

    @property
    def inputs(self) -> dict[str, typing.Any]:
        keys = self._attrs["inputs"].get("_keys")
        if keys is None:
            keys = [
                k
                for k in self._attrs["inputs"].keys()
                if self._attrs["inputs"][k] != None
            ]
        return {k: self._attrs["inputs"][k] for k in keys}

    @property
    def output(self) -> typing.Any:
        if self.status_code != "SUCCESS":
            return None
        keys = self._attrs["output"].get("_keys")
        if keys is None:
            keys = [
                k
                for k in self._attrs["output"].keys()
                if self._attrs["output"][k] != None
            ]
        output = {k: self._attrs["output"][k] for k in keys}
        if "_result" in output:
            return output["_result"]
        return output

    @property
    def parent_id(self) -> str:
        return self._attrs["parent_id"]

    def add_feedback(self, feedback: dict[str, typing.Any]) -> None:
        client = graph_client_context.require_graph_client()
        client.add_feedback(self.id, feedback)

    def feedback(self) -> WeaveIter[dict[str, typing.Any]]:
        client = graph_client_context.require_graph_client()
        return client.run_feedback(self.id)

    def parent(self) -> typing.Optional["Run"]:
        client = graph_client_context.require_graph_client()
        if self.parent_id == None:
            return None
        return client.run(self.parent_id)

    def children(self) -> WeaveIter["Run"]:
        client = graph_client_context.require_graph_client()
        return client.run_children(self.id)
