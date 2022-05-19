import os
import json
import typing

from . import errors
from . import artifacts_local
from . import weave_types as types
from . import mappers_python
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


def save_to_artifact(obj, artifact, name, type_):
    ref_extra = type_.save_instance(obj, artifact, name)
    with artifact.new_file(f"{name}.type.json") as f:
        json.dump(type_.to_dict(), f)

    ref_cls = (
        refs.WandbArtifactRef
        if isinstance(artifact, artifacts_local.WandbArtifact)
        else refs.LocalArtifactRef
    )
    artifact.save()
    return ref_cls(artifact, path=name, type=type_, obj=obj, extra=ref_extra)


def _get_name(wb_type: types.Type, obj: typing.Any) -> str:
    obj_names = util.find_names(obj)
    return f"{wb_type.name}-{obj_names[-1]}"


def _save_or_publish(obj, name=None, type=None, publish: bool = False):
    # TODO: get rid of this? Always type check?
    wb_type = type
    if wb_type is None:
        try:
            wb_type = types.TypeRegistry.type_of(obj)
        except errors.WeaveTypeError:
            raise errors.WeaveSerializeError("no weave type for object: ", obj)
    obj = box.box(obj)
    if name is None:
        name = _get_name(wb_type, obj)
    # TODO: refactor types to artifacts have a common base class
    artifact: typing.Any = None
    if publish:
        # TODO: Potentially add entity and project to namespace the artifact explicitly.
        artifact = artifacts_local.WandbArtifact(name, type=wb_type.name)
    else:
        artifact = artifacts_local.LocalArtifact(name)
    ref = save_to_artifact(obj, artifact, "_obj", wb_type)
    refs.put_ref(obj, ref)
    return ref


def publish(obj, name=None, type=None):
    # TODO: should we only expose save for our API with a "remote" flag or something
    return _save_or_publish(obj, name, type, True)


def save(obj, name=None, type=None):
    return _save_or_publish(obj, name, type, False)


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
