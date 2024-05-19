import os
import typing

from . import artifact_local
from . import ref_base
from . import weave_types as types
from . import graph
from . import runs
from . import errors


def get_obj_creator(ref: ref_base.Ref) -> typing.Optional[runs.Run]:
    # ref.backend.references(ref.artifact, "Run", {"dir": "input"})

    # creator = ref.backend.get_creator(ref.artifact)
    # # OR
    # backend = ref.backend.filter(type="Run", referenced=ref.artifact)
    # Extremely inefficient!
    # TODO
    for art_name in os.listdir(artifact_local.local_artifact_dir()):
        if (
            art_name.startswith("run-")
            and not art_name.endswith("-output")
            and artifact_local.local_artifact_exists(art_name, "latest")
        ):
            try:
                cache_obj = artifact_local.get_local_version(art_name, "latest")
            except errors.WeaveSerializeError:
                # This happens because we don't load all ecosystem modules, and so we can't
                # deserializes everything.
                continue

            def _is_creator(run):
                if isinstance(run.output, ref_base.Ref) and str(run.output) == str(ref):
                    # If any input is also the ref, this run did not create obj, since
                    # the obj already existed. This fixes an infinite loop where list-createIndexCheckpointTag
                    # which just returns its input would be treated as a the obj creator
                    # TODO: This whole thing is a pile of hacks, not production ready! Fix! We should
                    #     not need heuristics.
                    # TODO: for one, if we order all the artifacts by created_at, then
                    #     the first one will be the creator. Can't do that in this branch
                    #     since it doesn't have the created at change.
                    if any(str(input) == str(ref) for input in run.inputs.values()):
                        return False
                    return True

            if isinstance(cache_obj._ref.type, types.List):
                for run in cache_obj:
                    if _is_creator(run):
                        return run
            else:
                if _is_creator(cache_obj):
                    return cache_obj
    return None


def get_obj_expr(obj):
    obj_type = types.TypeRegistry.type_of(obj)
    if not isinstance(obj, ref_base.Ref):
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
    for artifact_name in os.listdir(artifact_local.local_artifact_dir()):
        if artifact_name.startswith("run-") and not artifact_name.endswith("-output"):
            run = artifact_local.get_local_version(artifact_name, "latest")
            if run is None:
                continue
            run_inputs = list(run.inputs.values())
            if run.op_name == op_name and run_inputs:
                input0 = run_inputs[0]
                if (
                    isinstance(input0, artifact_local.LocalArtifactRef)
                    and ref.uri == input0.uri
                ):
                    users.append(run)
    return users
