import os
import typing
import pathlib
import functools

from . import errors
from . import ref_base
from . import artifact_base
from . import artifact_mem
from . import artifact_fs
from . import artifact_local
from . import artifact_wandb
from . import weave_types as types
from . import mappers_python
from . import box
from . import errors
from . import graph

Ref = ref_base.Ref


def split_path_dotfile(path, dotfile_name):
    while path != "/":
        path, tail = os.path.split(path)
        if os.path.exists(os.path.join(path, dotfile_name)):
            return path, tail
    raise FileNotFoundError


def _get_name(wb_type: types.Type, obj: typing.Any) -> str:
    return wb_type.name
    # This tries to figure out which variable references obj.
    # But it is slow when there are a lot of references. If we want to do
    # something like this, we'll need to do it somewhere closer to user
    # interaction.
    # obj_names = util.find_names(obj)
    # return f"{wb_type.name}-{obj_names[-1]}"


def _save_or_publish(
    obj,
    name=None,
    type=None,
    publish: bool = False,
    artifact=None,
    branch=None,
):
    # HAX for W&B publishing.
    project = None
    if name is not None and "/" in name:
        project, name = name.split("/")
    source_branch = None
    if name is not None and ":" in name:
        name, source_branch = name.split(":", 1)

    if project is None and publish:
        project = artifact_wandb.DEFAULT_WEAVE_OBJ_PROJECT

    # source_branch = None
    # # If we have an existing ref and its a filesystem artifact
    # # track its branch
    # existing_ref = _get_ref(obj)
    # if isinstance(existing_ref, artifact_fs.FilesystemArtifactRef):
    #     # We don't branch across artifacts for now (name change)... But we could!
    #     if name is None or existing_ref.name == name:
    #         source_branch = existing_ref.branch

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
            from weave.mappers_publisher import map_to_python_remote

            artifact = artifact_wandb.WandbArtifact(name, type=wb_type.name)
            mapper = map_to_python_remote(wb_type, artifact)
            obj = mapper.apply(obj)
            panel_type = types.type_name_to_type("Panel")
            artifact._writeable_artifact.metadata["_weave_meta"] = {
                "is_weave_obj": True,
                "type_name": wb_type.name,
                "is_panel": panel_type and panel_type().assign_type(wb_type),
            }
        else:
            artifact = artifact_local.LocalArtifact(name, version=source_branch)
    ref = artifact.set("obj", wb_type, obj)

    # Only save if we have a ref into the artifact we created above. Otherwise
    #     nothing new was created, so just return the existing ref.
    if ref.artifact == artifact:
        if project is not None:
            artifact.save(project)
        else:
            artifact.save(branch=branch)

    return ref


def publish(obj, name=None, type=None):
    # TODO: should we only expose save for our API with a "remote" flag or something
    return _save_or_publish(obj, name, type, True)


def save(
    obj,
    name=None,
    type=None,
    artifact=None,
    branch=None,
) -> artifact_local.LocalArtifactRef:
    # print("STORAGE SAVE", name, obj, type, artifact)
    # ref = _get_ref(obj)
    # if ref is not None:
    #     if name is None or ref.artifact._name == name:
    #         return ref
    return _save_or_publish(obj, name, type, False, artifact=artifact, branch=branch)


def get(uri_s: typing.Union[str, ref_base.Ref]) -> typing.Any:
    if isinstance(uri_s, ref_base.Ref):
        return uri_s.get()
    return ref_base.Ref.from_str(uri_s).get()


get_local_version_ref = artifact_local.get_local_version_ref
get_local_version = artifact_local.get_local_version


def deref(ref):
    if isinstance(ref, ref_base.Ref):
        return ref.get()
    return ref


def _get_ref(obj: typing.Any) -> typing.Optional[ref_base.Ref]:
    if isinstance(obj, ref_base.Ref):
        return obj
    return ref_base.get_ref(obj)


def clear_ref(obj):
    ref_base.clear_ref(obj)


get_ref = _get_ref


# Return all local artifacts.
# Warning: may iterate a lot of the filesystem!
def local_artifacts() -> typing.List[artifact_local.LocalArtifact]:
    result = []
    obj_paths = sorted(
        pathlib.Path(artifact_local.local_artifact_dir()).iterdir(),
        key=os.path.getctime,
    )
    for art_path in obj_paths:
        if os.path.basename(art_path) != "tmp":
            result.append(artifact_local.LocalArtifact(art_path.name, None))
    return result


def all_objects():
    result = []
    obj_paths = sorted(
        pathlib.Path(artifact_local.local_artifact_dir()).iterdir(),
        key=os.path.getctime,
    )
    for art_path in obj_paths:
        ref = artifact_local.get_local_version_ref(art_path.name, "latest")
        if ref is not None:
            result.append((ref.created_at, ref))
    return [r[1] for r in sorted(result)]


def objects(
    of_type: types.Type, alias: str = "latest"
) -> typing.List[artifact_local.LocalArtifactRef]:
    result = []
    for art_name in os.listdir(artifact_local.local_artifact_dir()):
        try:
            ref = artifact_local.get_local_version_ref(art_name, alias)
            if ref is not None:
                if of_type.assign_type(ref.type):
                    # TODO: Why did I have this here?
                    # obj = ref.get()
                    # if isinstance(ref.type, types.RunType) and obj.op_name == "op-objects":
                    #     continue
                    result.append((ref.artifact.created_at, ref))
        except errors.WeaveSerializeError:
            # This happens because we may not have loaded ecosystem stuff that we need
            # to deserialize
            continue
    # Sorted by created_at
    return [r[1] for r in sorted(result)]


def recursively_unwrap_arrow(obj):
    if getattr(obj, "to_pylist_notags", None):
        return obj.to_pylist_notags()
    if getattr(obj, "as_py", None):
        return obj.as_py()
    if isinstance(obj, graph.Node):
        return obj
    if isinstance(obj, dict):
        return {k: recursively_unwrap_arrow(v) for (k, v) in obj.items()}
    elif isinstance(obj, list):
        return [recursively_unwrap_arrow(item) for item in obj]
    return obj


def to_python(obj, wb_type=None):
    if wb_type is None:
        wb_type = types.TypeRegistry.type_of(obj)
    # Note, we use ArtifactMem here, which means the serialized object
    # may have refs to non-saved objects.
    # TODO: need to revisit this as we start to use custom objects.
    mapper = mappers_python.map_to_python(wb_type, artifact_mem.MemArtifact())
    val = mapper.apply(obj)
    # TODO: this should be a ConstNode!
    return {"_type": wb_type.to_dict(), "_val": val}


def to_safe_const(obj):
    wb_type = types.TypeRegistry.type_of(obj)
    mapper = mappers_python.map_to_python(wb_type, artifact_mem.MemArtifact())
    val = mapper.apply(obj)
    return graph.ConstNode(wb_type, val)


def to_hashable(obj):
    wb_type = types.TypeRegistry.type_of(obj)
    art = artifact_mem.MemArtifact()
    mapper = mappers_python.map_to_python(wb_type, art)
    val = mapper.apply(obj)
    if art.ref_count() > 0:
        raise errors.WeaveSerializeError(
            "Cannot hash object that contains custom objects"
        )
    # TODO: this should be a ConstNode!
    return {"_type": wb_type.to_dict(), "_val": val}


def from_python(obj, wb_type=None):
    if wb_type is None:
        wb_type = types.TypeRegistry.type_from_dict(obj["_type"])
    mapper = mappers_python.map_from_python(wb_type, None)
    res = mapper.apply(obj["_val"])
    return res


def make_js_serializer():
    artifact = artifact_mem.MemArtifact()
    return functools.partial(to_weavejs, artifact=artifact)


def to_weavejs(obj, artifact: typing.Optional[artifact_base.Artifact] = None):
    from .ops_arrow import list_ as arrow_list

    obj = box.unbox(obj)
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    elif isinstance(obj, dict):
        return {k: to_weavejs(v, artifact=artifact) for (k, v) in obj.items()}
    elif isinstance(obj, list):
        return [to_weavejs(item, artifact=artifact) for item in obj]
    elif isinstance(obj, arrow_list.ArrowWeaveList):
        return obj.to_pylist_notags()
    wb_type = types.TypeRegistry.type_of(obj)

    if artifact is None:
        artifact = artifact_mem.MemArtifact()

    mapper = mappers_python.map_to_python(
        wb_type, artifact, mapper_options={"use_stable_refs": False}
    )
    return mapper.apply(obj)
