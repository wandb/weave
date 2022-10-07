import pyarrow as pa
import os
import json
import typing
import pathlib

from . import errors
from . import artifacts_local
from . import weave_types as types
from . import mappers_python
from . import box
from . import errors
from . import refs

Ref = refs.Ref


def split_path_dotfile(path, dotfile_name):
    while path != "/":
        path, tail = os.path.split(path)
        if os.path.exists(os.path.join(path, dotfile_name)):
            return path, tail
    raise FileNotFoundError


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
    # HAX for W&B publishing.
    project = None
    if name is not None and "/" in name:
        project, name = name.split("/")
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
    artifact.mapper = mappers_python.map_to_python(wb_type, artifact)
    ref = save_to_artifact(obj, artifact, "_obj", wb_type)

    # Only save if we have a ref into the artifact we created above. Otherwise
    #     nothing new was created, so just return the existing ref.
    if ref.artifact == artifact:
        if project is not None:
            artifact.save(project)
        else:
            artifact.save()
        refs.put_ref(obj, ref)

    return ref


def publish(obj, name=None, type=None):
    # TODO: should we only expose save for our API with a "remote" flag or something
    return _save_or_publish(obj, name, type, True)


save_mem = refs.save_mem


def save(obj, name=None, type=None, artifact=None) -> refs.LocalArtifactRef:
    # print("STORAGE SAVE", name, obj, type, artifact)
    # ref = _get_ref(obj)
    # if ref is not None:
    #     if name is None or ref.artifact._name == name:
    #         return ref
    return _save_or_publish(obj, name, type, False, artifact=artifact)


def get(uri_s):
    if isinstance(uri_s, refs.Ref):
        return uri_s.get()
    return refs.Ref.from_str(uri_s).get()


get_local_version = refs.get_local_version


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


def all_objects():
    result = []
    obj_paths = sorted(
        pathlib.Path(artifacts_local.local_artifact_dir()).iterdir(),
        key=os.path.getctime,
    )
    for art_path in obj_paths:
        ref = refs.get_local_version_ref(art_path.name, "latest")
        if ref is not None:
            result.append(ref)
    return result


def objects(of_type: types.Type, alias: str):
    result = []
    for art_name in os.listdir(artifacts_local.local_artifact_dir()):
        ref = refs.get_local_version_ref(art_name, alias)
        if ref is not None:
            if of_type.assign_type(ref.type) != types.Invalid():
                # TODO: Why did I have this here?
                # obj = ref.get()
                # if isinstance(ref.type, types.RunType) and obj.op_name == "op-objects":
                #     continue
                result.append(ref)
    return result


def to_python(obj):
    # Arrow hacks for WeaveJS. We want to send the raw Python data
    # to the frontend for these objects. But this will break querying them in Weave
    # Python when not using InProcessServer.
    # TODO: Remove!
    if getattr(obj, "to_pylist", None):
        obj = obj.to_pylist()
    elif getattr(obj, "as_py", None):
        obj = obj.as_py()

    wb_type = types.TypeRegistry.type_of(obj)
    mapper = mappers_python.map_to_python(
        wb_type, artifacts_local.LocalArtifact(_get_name(wb_type, obj))
    )
    val = mapper.apply(obj)
    # TODO: this should be a ConstNode!
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
