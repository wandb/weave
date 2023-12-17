import dataclasses
import hashlib
import json
import copy
import typing

from collections.abc import Mapping
from . import artifact_local
from . import storage
from . import ref_base
from . import weave_types as types
from .eager import WeaveIter
from .runs import Run


def refs_to_str(val: typing.Any) -> typing.Any:
    if isinstance(val, ref_base.Ref):
        return str(val)
    elif isinstance(val, dict):
        return {k: refs_to_str(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [refs_to_str(v) for v in val]
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
class GraphClientLocal:
    ##### Read API

    def find_op_run(
        self, op_name: str, inputs: dict[str, typing.Any]
    ) -> typing.Optional[Run]:
        run_id = make_run_id(op_name, inputs)
        return storage.get(f"local-artifact:///run-{run_id}:latest/obj")

    def ref_input_to(self, ref: artifact_local.LocalArtifactRef) -> list[Run]:
        runs = storage.objects(types.RunType())
        result = []
        for run_ref in runs:
            run = typing.cast(Run, run_ref.get())
            for k, v in run.inputs.items():
                if ref == v:
                    result.append(run)
        return result

    def ref_value_input_to(self, ref: artifact_local.LocalArtifactRef) -> list[Run]:
        runs = storage.objects(types.RunType())
        result = []
        for run_ref in runs:
            run = typing.cast(Run, run_ref.get())
            if ref.digest in run.inputs.get("_digests", []):
                result.append(run)
        return result

    def ref_is_own(self, ref: typing.Optional[ref_base.Ref]) -> bool:
        return isinstance(ref, artifact_local.LocalArtifactRef)

    ##### Write API

    def save_object(
        self, obj: typing.Any, name: str, branch_name: str
    ) -> artifact_local.LocalArtifactRef:
        from . import storage

        return storage._direct_save(
            obj,
            name=name,
            branch_name=branch_name,
        )

    def create_run(
        self,
        op_name: str,
        parent: typing.Optional["Run"],
        inputs: typing.Dict[str, typing.Any],
        input_refs: list[artifact_local.LocalArtifactRef],
    ) -> Run:
        run_id = make_run_id(op_name, inputs)
        with_digest_inputs = copy.copy(inputs)
        with_digest_inputs["_digests"] = [ref.digest for ref in input_refs]
        return Run(run_id, op_name, inputs=with_digest_inputs)

    def fail_run(self, run: Run, exception: Exception) -> None:
        raise NotImplementedError

    def finish_run(
        self,
        run: Run,
        output: typing.Any,
        output_refs: list[artifact_local.LocalArtifactRef],
    ) -> None:
        run.output = output
        self.save_object(run, f"run-{run.id}", "latest")
