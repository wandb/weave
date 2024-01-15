import dataclasses
import hashlib
import json
import copy
import typing
from typing import Sequence, Sequence

from collections.abc import Mapping
from .graph_client import GraphClient
from .op_def import OpDef
from .ref_base import Ref
from . import artifact_local
from . import storage
from . import ref_base
from . import weave_types as types
from .run import RunKey, Run
from .runs import Run as WeaveRunObj


def refs_to_str(val: typing.Any) -> typing.Any:
    if isinstance(val, ref_base.Ref):
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


def make_run_id(op_name: str, inputs: dict[str, typing.Any]) -> str:
    input_hash = hash_inputs(inputs)
    hasher = hashlib.md5()
    hasher.update(op_name.encode())
    hasher.update(input_hash.encode())
    return hasher.hexdigest()


@dataclasses.dataclass
class GraphClientLocal(GraphClient[WeaveRunObj]):
    ##### Read API

    # Implement the required members from the "GraphClient" protocol class
    def runs(self) -> Sequence[Run]:
        runs = storage.objects(types.RunType())
        result: list[WeaveRunObj] = []
        for run in runs:
            result.append(typing.cast(WeaveRunObj, run.get()))
        return result

    def run(self, run_id: str) -> typing.Optional[Run]:
        raise NotImplementedError

    def find_op_run(
        self, op_name: str, inputs: dict[str, typing.Any]
    ) -> typing.Optional[Run]:
        run_id = make_run_id(op_name, inputs)
        return storage.get(f"local-artifact:///run-{run_id}:latest/obj")

    def run_children(self, run_id: str) -> Sequence[Run]:
        raise NotImplementedError

    def op_runs(self, op_def: OpDef) -> Sequence[Run]:
        runs = storage.objects(types.RunType())
        result: list[WeaveRunObj] = []
        for run_ref in runs:
            run = typing.cast(WeaveRunObj, run_ref.get())
            if run.op_name == str(op_def.location):
                result.append(run)
        return result

    def ref_input_to(self, ref: Ref) -> Sequence[Run]:
        runs = storage.objects(types.RunType())
        result: list[WeaveRunObj] = []
        for run_ref in runs:
            run = typing.cast(WeaveRunObj, run_ref.get())
            for v in run.inputs.values():
                if str(ref) == str(v):
                    result.append(run)
        return result

    def ref_value_input_to(self, ref: Ref) -> list[Run]:
        runs = storage.objects(types.RunType())
        result: list[Run] = []
        for run_ref in runs:
            run = typing.cast(WeaveRunObj, run_ref.get())
            if ref.digest in run.inputs.get("_digests", []):
                result.append(run)
        return result

    def ref_output_of(self, ref: Ref) -> typing.Optional[Run]:
        runs = storage.objects(types.RunType())
        for run_ref in runs:
            run = typing.cast(WeaveRunObj, run_ref.get())
            if str(ref) == str(run.output):
                return run
        return None

    def run_feedback(self, run_id: str) -> Sequence[dict[str, typing.Any]]:
        raise NotImplementedError

    def feedback(self, feedback_id: str) -> typing.Optional[dict[str, typing.Any]]:
        raise NotImplementedError

    # Helpers

    def ref_is_own(self, ref: typing.Optional[ref_base.Ref]) -> bool:
        return isinstance(ref, artifact_local.LocalArtifactRef)

    def ref_uri(
        self, name: str, version: str, path: str
    ) -> artifact_local.WeaveLocalArtifactURI:
        return artifact_local.WeaveLocalArtifactURI(name, version, path=path)

    def run_ui_url(self, run: Run) -> str:
        raise NotImplementedError

    ##### Write API

    def save_object(
        self, obj: typing.Any, name: str, branch_name: str
    ) -> artifact_local.LocalArtifactRef:
        from . import storage

        return storage.direct_save(
            obj,
            name=name,
            branch_name=branch_name,
        )

    def create_run(
        self,
        op_name: str,
        parent: typing.Optional["RunKey"],
        inputs: typing.Dict[str, typing.Any],
        input_refs: Sequence[Ref],
    ) -> WeaveRunObj:
        run_id = make_run_id(op_name, inputs)
        with_digest_inputs = copy.copy(inputs)
        with_digest_inputs["_digests"] = [ref.digest for ref in input_refs]
        return WeaveRunObj(run_id, op_name, inputs=with_digest_inputs)

    def fail_run(self, run: Run, exception: BaseException) -> None:
        # TODO: Need to implement for local, for now just do nothing.
        pass

    def finish_run(
        self,
        run: WeaveRunObj,
        output: typing.Any,
        output_refs: Sequence[Ref],
    ) -> None:
        run.output = self.save_object(output, f"run-{run.id}-output", "latest")
        ref_base._put_ref(output, run.output)
        self.save_object(run, f"run-{run.id}", "latest")

    def add_feedback(self, run_id: str, feedback: typing.Any) -> None:
        raise NotImplementedError
