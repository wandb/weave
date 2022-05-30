from collections.abc import Mapping
import pyarrow as pa
import os
import json
import typing
from urllib.parse import urlparse

from . import errors
from . import arrow_util
from . import artifacts_local
from . import weave_types as types
from . import mappers_python
from . import mappers_arrow
from . import graph
from . import util
from . import box
from . import refs
from .artifacts_local import LOCAL_ARTIFACT_DIR

Ref = refs.Ref


def split_path_dotfile(path, dotfile_name):
    while path != "/":
        path, tail = os.path.split(path)
        if os.path.exists(os.path.join(path, dotfile_name)):
            return path, tail
    raise FileNotFoundError


MEM_OBJS: typing.Dict[str, typing.Any] = {}


class MemRef(refs.Ref):
    def __init__(self, name):
        self.name = name

    def get(self):
        return MEM_OBJS[self.name]

    def __str__(self):
        return self.name


def save_mem(obj, name):
    MEM_OBJS[name] = obj
    return MemRef(name)


def save_to_artifact(obj, artifact: artifacts_local.LocalArtifact, name, type_):
    # Tell types what name to use if not obj
    # We need to fix the save/load API so this is unnecessary.
    # This is also necessary to prevent saving the same obj at different
    # key paths (as the Default mappers try to do now). That breaks saving
    # references in new objects currently. Will be fixed when we make saving
    # references to existing artifacts work.
    # TODO: Fix
    # DO NOT MERGE
    if name != "_obj":
        name = type_.name
    ref_extra = type_.save_instance(obj, artifact, name)
    if name != "_obj":
        # Warning: This is hacks to force files to be content addressed
        # If the type saved a file, rename with its content hash included
        #     in its name.
        # TODO: fix
        # DO NOT MERGE
        hash = artifact.make_last_file_content_addressed()
        if hash is not None:
            name = f"{hash}-{name}"
    return refs.LocalArtifactRef(
        artifact, path=name, type=type_, obj=obj, extra=ref_extra
    )


def save(obj, name=None, type=None, artifact=None):
    ref = _get_ref(obj)
    if ref is not None:
        if name is None or ref.artifact._name == name:
            return ref
    # TODO: get rid of this? Always type check?
    wb_type = type
    if wb_type is None:
        try:
            wb_type = types.TypeRegistry.type_of(obj)
        except errors.WeaveTypeError as e:
            raise errors.WeaveSerializeError(
                "weave type error during serialization for object: %s. %s"
                % (obj, str(e.args))
            )
    obj = box.box(obj)
    if artifact is None:
        if name is None:
            obj_names = util.find_names(obj)
            # name = f"{wb_type.name}-{obj_names[-1]}-{util.rand_string_n(10)}"
            name = f"{wb_type.name}-{obj_names[-1]}"
        artifact = artifacts_local.LocalArtifact(name)
    ref = save_to_artifact(obj, artifact, "_obj", wb_type)
    with artifact.new_file(f"_obj.type.json") as f:
        json.dump(wb_type.to_dict(), f)
    artifact.save()
    refs.put_ref(obj, ref)
    return ref


def get(uri_s):
    if isinstance(uri_s, refs.Ref):
        return uri_s.get()
    ref = refs.LocalArtifactRef.from_str(uri_s)
    return ref.get()


def deref(ref):
    if isinstance(ref, refs.Ref):
        return ref.get()
    return ref


def _get_ref(obj):
    if isinstance(obj, refs.Ref):
        return obj
    return refs.get_ref(obj)


def clear_ref(obj):
    refs.clear_ref(obj)


get_ref = _get_ref


def get_version(name, version):
    # TODO: Watch out, this is a major race!
    #   - We need to eliminate this race or allow duplicate objectcs in parallel
    #     and then resolve later.
    #   - This is especially a problem for creating Runs and async Runs. We may
    #     accidentally launch parallel runs with the same run ID!
    if not artifacts_local.local_artifact_exists(name, version):
        return None
    art = artifacts_local.LocalArtifact(name, version)
    ref = refs.LocalArtifactRef(art, path="_obj")
    return ref.get()


def get_obj_creator(obj_ref):
    # Extremely inefficient!
    # TODO
    for art_name in os.listdir(LOCAL_ARTIFACT_DIR):
        if (
            art_name.startswith("run-")
            and not art_name.endswith("-output")
            and artifacts_local.local_artifact_exists(art_name, "latest")
        ):
            run = get("%s/latest" % art_name)
            if isinstance(run._output, refs.Ref) and str(run._output) == str(obj_ref):
                # If any input is also the ref, this run did not create obj, since
                # the obj already existed. This fixes an infinite loop where list-indexCheckpoint
                # which just returns its input would be treated as a the obj creator
                # TODO: This whole thing is a pile of hacks, not production ready! Fix! We should
                #     not need heuristics.
                # TODO: for one, if we order all the artifacts by created_at, then
                #     the first one will be the creator. Can't do that in this branch
                #     since it doesn't have the created at change.
                if any(str(input) == str(obj_ref) for input in run._inputs.values()):
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
        obj_type.object_type,
        run._op_name,
        {k: get_obj_expr(input) for k, input in run._inputs.items()},
    )


def to_python(obj):
    # Arrow hacks for WeaveJS. We want to send the raw Python data
    # to the frontend for these objects. But this will break querying them in Weave
    # Python when not using InProcessServer.
    # TODO: Remove!
    if hasattr(obj, "to_pylist"):
        return obj.to_pylist()
    elif hasattr(obj, "as_py"):
        return obj.as_py()

    wb_type = types.TypeRegistry.type_of(obj)
    artifact = artifacts_local.LocalArtifact("to-python-%s" % wb_type.name)
    mapper = mappers_python.map_to_python(wb_type, artifact)
    val = mapper.apply(obj)
    return {"_type": wb_type.to_dict(), "_val": val}


def from_python(obj):
    wb_type = types.TypeRegistry.type_from_dict(obj["_type"])
    mapper = mappers_python.map_from_python(wb_type, None)
    res = mapper.apply(obj["_val"])
    return res


def to_arrow(obj):
    wb_type = types.TypeRegistry.type_of(obj)
    artifact = artifacts_local.LocalArtifact("to-arrow-%s" % wb_type.name)
    if isinstance(wb_type, types.List):
        object_type = wb_type.object_type

        # Convert to arrow, serializing Custom objects to the artifact
        mapper = mappers_arrow.map_to_arrow(object_type, artifact)
        pyarrow_type = mapper.result_type()
        py_objs = (mapper.apply(o) for o in obj)

        # TODO: do I need this branch? Does it work now?
        # if isinstance(wb_type.object_type, types.ObjectType):
        #     arrow_obj = pa.array(py_objs, pyarrow_type)
        from .ops_primitives import arrow

        if pa.types.is_struct(pyarrow_type):
            arr = pa.array(py_objs, type=pyarrow_type)
            rb = pa.RecordBatch.from_struct_array(arr)  # this pivots to columnar layout
            arrow_obj = pa.Table.from_batches([rb])
        else:
            arrow_obj = pa.array(py_objs, pyarrow_type)
        weave_obj = arrow.ArrowWeaveList(arrow_obj, object_type, artifact)

        # Save the weave object to the artifact
        ref = save(weave_obj, artifact=artifact)

        return ref.obj

    raise errors.WeaveInternalError("to_arrow not implemented for: %s" % obj)


def from_arrow(obj):
    wb_type = types.TypeRegistry.type_from_dict(obj["_type"])
    mapper = mappers_arrow.map_from_arrow(wb_type, None)
    res = mapper.apply(obj["_val"])
    return res
