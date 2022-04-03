from collections.abc import Mapping
import os
import json
import typing
from urllib.parse import urlparse

from . import errors
from . import artifacts_local
from . import weave_types as types
from . import mappers_python
from . import graph
from . import util
from . import box
from . import refs

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


def save(obj, name=None, type=None, artifact=None):
    # TODO: get rid of this? Always type check?
    wb_type = type
    if wb_type is None:
        wb_type = types.TypeRegistry.type_of(obj)
    if wb_type is None:
        raise errors.WeaveSerializeError("no weave type for object: ", obj)
    # print("WB_TYPE", wb_type)
    if not hasattr(wb_type, "save_instance"):
        print("NO SAVE INSTANCE", wb_type, obj)
        return obj
    obj = box.box(obj)
    if name is None:
        obj_names = util.find_names(obj)
        # name = f"{wb_type.name}-{obj_names[-1]}-{util.rand_string_n(10)}"
        name = f"{wb_type.name}-{obj_names[-1]}"
    if artifact is None:
        artifact = artifacts_local.LocalArtifact(name)
    saved_type = wb_type.save_instance(obj, artifact, "_obj")
    # print("SAVED_TYPE", saved_type)
    with artifact.new_file("_obj.type.json") as f:
        json.dump(saved_type.to_dict(), f)
    artifact.save()
    ref = refs.LocalArtifactRef(artifact, path="_obj", type=saved_type, obj=obj)
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
    for art_name in os.listdir("local-artifacts"):
        if (
            art_name.startswith("run-")
            and not art_name.endswith("-output")
            and artifacts_local.local_artifact_exists(art_name, "latest")
        ):
            run = get("%s/latest" % art_name)
            if isinstance(run._output, refs.Ref) and str(run._output) == str(obj_ref):
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
    mapper = mappers_python.map_to_python(wb_type, None)
    val = mapper.apply(obj)
    return {"_type": wb_type.to_dict(), "_val": val}


def from_python(obj):
    wb_type = types.TypeRegistry.type_from_dict(obj["_type"])
    mapper = mappers_python.map_from_python(wb_type, None)
    res = mapper.apply(obj["_val"])
    return res
