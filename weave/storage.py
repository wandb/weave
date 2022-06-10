import pyarrow as pa
import os
import json
import typing

from . import errors
from . import artifacts_local
from . import weave_types as types
from . import mappers_python
from . import mappers_arrow
from . import graph
from . import util
from . import box
from . import errors
from . import refs
from . import uris

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
        self._name = name

    @property
    def name(self):
        return self._name

    def get(self):
        return MEM_OBJS[self.name]

    def __str__(self):
        return self.name


def save_mem(obj, name):
    MEM_OBJS[name] = obj
    return MemRef(name)


def save_to_artifact(obj, artifact: artifacts_local.LocalArtifact, name, type_):
    # print("SAVE TO ARTIFACT", obj, artifact, name, type_)
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
    # If save_instance returned a Ref, return that directly.
    # TODO: refactor
    if isinstance(ref_extra, refs.Ref):
        return ref_extra
    if name != "_obj":
        # Warning: This is hacks to force files to be content addressed
        # If the type saved a file, rename with its content hash included
        #     in its name.
        # TODO: fix
        # DO NOT MERGE
        hash = artifact.make_last_file_content_addressed()
        if hash is not None:
            name = f"{hash}-{name}"
    with artifact.new_file(f"{name}.type.json") as f:
        json.dump(type_.to_dict(), f)
        artifact._last_write_path = None
    # TODO: return ObjectRootRef (ArtifactRootRef?) here
    return refs.LocalArtifactRef(
        artifact, path=name, type=type_, obj=obj, extra=ref_extra
    )
    # Jason's code does this, however, we can't do that, since save_to_artifact()
    # needs to return an artifact local ref (the artifact is not yet saved at this
    # point).
    # ref_cls = (
    #     refs.WandbArtifactRef
    #     if isinstance(artifact, artifacts_local.WandbArtifact)
    #     else refs.LocalArtifactRef
    # )
    # return ref_cls(artifact, path=name, type=type_, obj=obj, extra=ref_extra)


def _get_name(wb_type: types.Type, obj: typing.Any) -> str:
    return wb_type.name
    # This tries to figure out which variable references obj.
    # But it is slow when there are a lot of references. If we want to do
    # something like this, we'll need to do it somewhere closer to user
    # interaction.
    # obj_names = util.find_names(obj)
    # return f"{wb_type.name}-{obj_names[-1]}"


def _save_or_publish(obj, name=None, type=None, publish: bool = False, artifact=None):
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
            name = _get_name(wb_type, obj)
        # TODO: refactor types to artifacts have a common base class
        if publish:
            # TODO: Potentially add entity and project to namespace the artifact explicitly.
            artifact = artifacts_local.WandbArtifact(name, type=wb_type.name)
        else:
            artifact = artifacts_local.LocalArtifact(name)
    ref = save_to_artifact(obj, artifact, "_obj", wb_type)

    # Only save if we have a ref into the artifact we created above. Otherwise
    #     nothing new was created, so just return the existing ref.
    if ref.artifact == artifact:
        artifact.save()
        refs.put_ref(obj, ref)

    return ref


def publish(obj, name=None, type=None):
    # TODO: should we only expose save for our API with a "remote" flag or something
    return _save_or_publish(obj, name, type, True)


def save(obj, name=None, type=None, artifact=None):
    # print("STORAGE SAVE", name, obj, type, artifact)
    # ref = _get_ref(obj)
    # if ref is not None:
    #     if name is None or ref.artifact._name == name:
    #         return ref
    return _save_or_publish(obj, name, type, False, artifact=artifact)


def get(uri_s):
    if isinstance(uri_s, refs.Ref):
        return uri_s.get()
    location = uris.WeaveURI.parse(uri_s)
    # TODO: refactor mem ref with runtimeobject location and use a single branch
    # here on the base ref/uri class
    if isinstance(location, uris.WeaveLocalArtifactURI):
        ref = location.to_ref()
    elif isinstance(location, uris.WeaveWBArtifactURI):
        ref = location.to_ref()
    elif isinstance(location, uris.WeaveRuntimeURI):
        ref = MemRef(uri_s)
    else:
        raise errors.WeaveInternalError(f"Unsupported URI str: {uri_s}")
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
    for art_name in os.listdir(artifacts_local.LOCAL_ARTIFACT_DIR):
        if (
            art_name.startswith("run-")
            and not art_name.endswith("-output")
            and artifacts_local.local_artifact_exists(art_name, "latest")
        ):
            local_uri = uris.WeaveLocalArtifactURI.make_uri(
                artifacts_local.LOCAL_ARTIFACT_DIR, art_name, "latest"
            )
            run = get(local_uri)
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
        obj = obj.to_pylist()
    elif hasattr(obj, "as_py"):
        obj = obj.as_py()

    wb_type = types.TypeRegistry.type_of(obj)
    mapper = mappers_python.map_to_python(
        wb_type, artifacts_local.LocalArtifact(_get_name(wb_type, obj))
    )
    val = mapper.apply(obj)
    return {"_type": wb_type.to_dict(), "_val": val}


def from_python(obj):
    wb_type = types.TypeRegistry.type_from_dict(obj["_type"])
    mapper = mappers_python.map_from_python(
        wb_type, artifacts_local.LocalArtifact(_get_name(wb_type, obj))
    )
    res = mapper.apply(obj["_val"])
    return res


# Converting table algorithm
# construct the parquet file
#     first, determine type of raw table data
#        this is done by mapping weave type to arrow type
#     then write
# Then construct a WeaveList, with the weave type and which artifact it came from
# Then save the WeaveList...
# So we don't actually have to save it.

# This will be a faster version fo to_arrow (below). Its
# used in op file-table, to convert from a wandb Table to Weave
# (that code is very experimental and not totally working yet)
def to_arrow_from_list_and_artifact(obj, object_type, artifact):
    import time

    start_time = time.time()

    # Get what the parquet type will be.
    mapper = mappers_arrow.map_to_arrow(object_type, artifact)
    pyarrow_type = mapper.result_type()

    # TODO: do I need this branch? Does it work now?
    # if isinstance(wb_type.object_type, types.ObjectType):
    #     arrow_obj = pa.array(py_objs, pyarrow_type)
    from .ops_primitives import arrow

    import time

    if pa.types.is_struct(pyarrow_type):
        fields = list(pyarrow_type)
        schema = pa.schema(fields)
        arrow_obj = pa.Table.from_pylist(obj, schema=schema)
    else:
        arrow_obj = pa.array(obj, pyarrow_type)
    print("arrow_obj time: %s" % (time.time() - start_time))
    start_time = time.time()
    weave_obj = arrow.ArrowWeaveList(arrow_obj, object_type, artifact)
    return weave_obj


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
