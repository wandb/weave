import os
import typing

from . import artifacts_local
from . import refs
from . import weave_types as types
from . import graph
from . import runs


def get_obj_creator(ref: refs.Ref) -> typing.Optional[runs.Run]:
    # ref.backend.references(ref.artifact, "Run", {"dir": "input"})

    # creator = ref.backend.get_creator(ref.artifact)
    # # OR
    # backend = ref.backend.filter(type="Run", referenced=ref.artifact)
    # Extremely inefficient!
    # TODO
    for art_name in os.listdir(artifacts_local.local_artifact_dir()):
        if (
            art_name.startswith("run-")
            and not art_name.endswith("-output")
            and artifacts_local.local_artifact_exists(art_name, "latest")
        ):
            run = refs.get_local_version(art_name, "latest")
            if isinstance(run.output, refs.Ref) and str(run.output) == str(ref):
                # If any input is also the ref, this run did not create obj, since
                # the obj already existed. This fixes an infinite loop where list-createIndexCheckpointTag
                # which just returns its input would be treated as a the obj creator
                # TODO: This whole thing is a pile of hacks, not production ready! Fix! We should
                #     not need heuristics.
                # TODO: for one, if we order all the artifacts by created_at, then
                #     the first one will be the creator. Can't do that in this branch
                #     since it doesn't have the created at change.
                if any(str(input) == str(ref) for input in run.inputs.values()):
                    continue
                return run
    return None


def get_obj_expr(obj):
    obj_type = types.TypeRegistry.type_of(obj)
    if not isinstance(obj, refs.Ref):
        return graph.ConstNode(obj_type, obj)
    run = get_obj_creator(obj)
    if run is None:
        return graph.ConstNode(obj_type, obj)
    return graph.OutputNode(
        obj.type,
        run.op_name,
        {k: get_obj_expr(input) for k, input in run.inputs.items()},
    )


def used_by(ref, op_name: str) -> list[runs.Run]:
    users = []
    for artifact_name in os.listdir(artifacts_local.local_artifact_dir()):
        if artifact_name.startswith("run-") and not artifact_name.endswith("-output"):
            run = refs.get_local_version(artifact_name, "latest")
            if run is None:
                continue
            run_inputs = list(run.inputs.values())
            if run.op_name == op_name and run_inputs:
                input0 = run_inputs[0]
                if isinstance(input0, refs.LocalArtifactRef) and ref.uri == input0.uri:
                    users.append(run)
    return users
