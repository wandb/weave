from collections.abc import Mapping
import contextlib
import hashlib
import os
import pathlib
import json
import shutil
from urllib.parse import urlparse

from . import errors
from . import weave_types as types
from . import mappers_python
from . import graph
from . import util
from . import box


# stack of contexts
context = []


class WeaveContext(object):
    def __init__(self, storage_type):
        if storage_type == "local_file":
            self.storage = None
            # self.storage = LocalFileStorage('/tmp')
        elif storage_type == "hdf5":
            self.storage = None
            # self.storage = H5FileStorage('/tmp')
        self.object_refs = {}

    def __enter__(self):
        context.append(self)

    def __exit__(self, exc_type, exc_value, exc_traceback):
        context.pop()


def get_context():
    if not context:
        context.append(WeaveContext("local_file"))
    return context[-1]


def get_object_ref(obj):
    return get_context().object_refs.get(id(obj))


# From sdk/interface/artifacts.py
def md5_hash_file(path):
    hash_md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def md5_string(string: str) -> str:
    hash_md5 = hashlib.md5()
    hash_md5.update(string.encode())
    return hash_md5.hexdigest()


# This is a prototype implementation. Chock full of races, and other
# problems
# Do not use in prod!
class LocalArtifact:
    def __init__(self, name, version=None):
        self._name = name
        self._version = version
        self._root = os.path.join("local-artifacts", name)
        os.makedirs(self._root, exist_ok=True)
        self._setup_dirs()

        pathlib.Path(os.path.join(self._root, ".wandb-artifact")).touch()

    @property
    def version(self):
        if self._version is None:
            raise Exception("artifact must be saved before calling version!")
        return self._version

    def _setup_dirs(self):
        self._write_dirname = os.path.join(
            self._root, "working-%s" % util.rand_string_n(12)
        )
        self._read_dirname = None
        if self._version:
            self._read_dirname = os.path.join(self._root, self._version)

            # if this is a branch, set to the actual specific version it points to
            if os.path.islink(self._read_dirname):
                self._version = os.path.basename(os.path.realpath(self._read_dirname))
                self._read_dirname = os.path.join(self._root, self._version)

    @property
    def abs_root(self):
        return os.path.abspath(self._dir_name)

    @contextlib.contextmanager
    def new_file(self, path, binary=False):
        os.makedirs(self._write_dirname, exist_ok=True)
        mode = "w"
        if binary:
            mode = "wb"
        f = open(os.path.join(self._write_dirname, path), mode)
        yield f
        f.close()

    @contextlib.contextmanager
    def open(self, path, binary=False):
        mode = "r"
        if binary:
            mode = "rb"
        f = open(os.path.join(self._read_dirname, path), mode)
        yield f
        f.close()

    def save(self, branch="latest"):
        manifest = {}
        if self._read_dirname:
            for dirpath, dnames, fnames in os.walk(self._read_dirname):
                for f in fnames:
                    full_path = os.path.join(dirpath, f)
                    manifest[f] = md5_hash_file(full_path)
        for dirpath, dnames, fnames in os.walk(self._write_dirname):
            for f in fnames:
                full_path = os.path.join(dirpath, f)
                manifest[f] = md5_hash_file(full_path)
        commit_hash = md5_string(json.dumps(manifest, sort_keys=True, indent=2))
        self._version = commit_hash
        if os.path.exists(os.path.join(self._root, commit_hash)):
            # already have this version!
            pass
        else:
            new_dirname = os.path.join(self._root, commit_hash)
            os.makedirs(new_dirname, exist_ok=True)
            if self._read_dirname:
                for path in os.listdir(self._read_dirname):
                    src_path = os.path.join(self._read_dirname, path)
                    target_path = os.path.join(new_dirname, path)
                    if os.path.isdir(full_path):
                        shutil.copytree(src_path, target_path)
                    else:
                        shutil.copyfile(src_path, target_path)
            for path in os.listdir(self._write_dirname):
                src_path = os.path.join(self._write_dirname, path)
                target_path = os.path.join(new_dirname, path)
                if os.path.isdir(full_path):
                    shutil.copytree(src_path, target_path)
                else:
                    shutil.copyfile(src_path, target_path)
        shutil.rmtree(self._write_dirname)
        self._setup_dirs()

        # Example of one of many races here
        link_name = os.path.join(self._root, branch)
        if os.path.exists(link_name):
            os.remove(link_name)
        os.symlink(self._version, link_name)

    def uri(self, path=None):
        return LocalArtifactUri(self, path)


def split_path_dotfile(path, dotfile_name):
    while path != "/":
        path, tail = os.path.split(path)
        if os.path.exists(os.path.join(path, dotfile_name)):
            return path, tail
    raise FileNotFoundError


class LocalArtifactUri:
    def __init__(self, artifact, path=None):
        self.artifact = artifact
        self.path = path
        if self.path is None:
            self.path = "_obj"

    @property
    def type(self):
        with self.artifact.open(f"{self.path}.type.json") as f:
            type_json = json.load(f)
        return types.TypeRegistry.type_from_dict(type_json)

    @classmethod
    def from_str(cls, s):
        # Commented out the more complicated full URI so that
        # the demo looks nicer
        # TODO: fix.
        # url = urlparse(s)
        # if url.scheme != "local-artifact":
        #     raise Exception("invalid")
        # artifact_root, path = split_path_dotfile(url.path, ".wandb-artifact")
        if "/" not in s:
            return cls(LocalArtifact(s), "_obj")
        parts = s.split("/", 2)
        if len(parts) == 2:
            return cls(LocalArtifact(parts[0], version=parts[1]), "_obj")
        return cls(LocalArtifact(parts[0], version=parts[1]), parts[2])

    def __str__(self):
        # TODO: this is no good! We always refer to "latest"
        #    but we should actually refer to specific versions.
        # But then when we're mutating, we need to know which branch to
        #    mutate...
        artifact_version = self.artifact._name + "/" + self.artifact.version
        if self.path == "_obj":
            return artifact_version
        return artifact_version + "/" + self.path
        # artifact_uri = f"local-artifact://{self.artifact.abs_root}"
        # if self.path is not None:
        #     return f"{artifact_uri}/{self.path}"
        # return artifact_uri


def local_artifact_exists(name, branch):
    return os.path.exists(os.path.join("local-artifacts", name, branch))


OBJ_REFS: Mapping[str, "Ref"] = {}


def get_ref(obj):
    if hasattr(obj, "_ref"):
        return obj._ref
    return None


def put_ref(obj, ref):
    obj._ref = ref


class Ref:
    pass

    def _ipython_display_(self):
        from . import show

        return show(self)


class LocalArtifactRef(Ref):
    uri: LocalArtifactUri

    def __init__(self, type, uri, obj=None):
        self.type = type
        self.uri = uri
        self.obj = obj

    def to_json(self):
        return {"type": self.type.to_dict(), "uri": str(self.uri)}

    @classmethod
    def from_json(cls, val):
        if isinstance(val, dict) and "type" in val and "uri" in val:
            return cls(
                types.TypeRegistry.type_from_dict(val["type"]),
                LocalArtifactUri.from_str(val["uri"]),
            )
        else:
            return None

    def get(self):
        obj = self.type.load_instance(self.uri.artifact, self.uri.path)
        obj = box.box(obj)
        put_ref(obj, self)
        return obj

    def versions(self):
        artifact_path = os.path.join("local-artifacts", self.uri.artifact._name)
        versions = []
        for version_name in os.listdir(artifact_path):
            if (
                not os.path.islink(os.path.join(artifact_path, version_name))
                and not version_name.startswith("working")
                and not version_name.startswith(".")
            ):
                # This is ass-backward, have to get the full object to just
                # get the ref.
                # TODO
                obj = get_version(self.uri.artifact._name, version_name)
                ref = get_ref(obj)
                versions.append(ref)
        return versions

    def __str__(self):
        return str(self.uri)


types.LocalArtifactRefType.instance_class = LocalArtifactRef
types.LocalArtifactRefType.instance_classes = LocalArtifactRef


MEM_OBJS = {}


class MemRef(Ref):
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
        artifact = LocalArtifact(name)
    saved_type = wb_type.save_instance(obj, artifact, "_obj")
    # print("SAVED_TYPE", saved_type)
    with artifact.new_file("_obj.type.json") as f:
        json.dump(saved_type.to_dict(), f)
    artifact.save()
    ref = LocalArtifactRef(saved_type, artifact.uri("_obj"), obj)
    put_ref(obj, ref)
    return ref


def get(uri_s):
    if isinstance(uri_s, Ref):
        return uri_s.get()
    uri = LocalArtifactUri.from_str(uri_s)
    with uri.artifact.open("_obj.type.json") as f:
        type_json = json.load(f)
    wb_type = types.TypeRegistry.type_from_dict(type_json)
    ref = LocalArtifactRef(wb_type, uri)
    obj = ref.get()
    return obj


def deref(ref):
    if isinstance(ref, Ref):
        return ref.get()
    return ref


def _get_ref(obj):
    if isinstance(obj, Ref):
        return obj
    ref = get_ref(obj)
    return ref


def get_version(name, version):
    # TODO: Watch out, this is a major race!
    #   - We need to eliminate this race or allow duplicate objectcs in parallel
    #     and then resolve later.
    #   - This is especially a problem for creating Runs and async Runs. We may
    #     accidentally launch parallel runs with the same run ID!
    if not local_artifact_exists(name, version):
        return None
    art = LocalArtifact(name, version)
    art_uri = LocalArtifactUri(art)
    return get(str(art_uri))


def get_obj_creator(obj_ref):
    # Extremely inefficient!
    # TODO
    for art_name in os.listdir("local-artifacts"):
        if (
            art_name.startswith("run-")
            and not art_name.endswith("-output")
            and local_artifact_exists(art_name, "latest")
        ):
            run = get("%s/latest" % art_name)
            if isinstance(run._output, Ref) and str(run._output) == str(obj_ref):
                return run
    return None


def get_obj_expr(obj):
    obj_type = types.TypeRegistry.type_of(obj)
    if not isinstance(obj, Ref):
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
