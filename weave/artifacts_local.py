import contextlib
import functools
import hashlib
import os
import json
import shutil
from datetime import datetime
import pathlib
import tempfile
import typing

from . import uris
from . import util
from . import errors
from . import wandb_api
import wandb


@functools.lru_cache(1000)
def get_wandb_read_artifact(path):
    return wandb_api.wandb_public_api().artifact(path)


def local_artifact_dir() -> str:
    return os.environ.get("WEAVE_LOCAL_ARTIFACT_DIR") or os.path.join(
        "/tmp", "local-artifacts"
    )


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


def local_artifact_exists(name: str, branch: str) -> bool:
    return os.path.exists(os.path.join(local_artifact_dir(), name, branch))


class Artifact:
    name: str

    @property
    def is_saved(self) -> bool:
        raise NotImplementedError()

    @contextlib.contextmanager
    def open(self, path: str, binary: bool = False):
        raise NotImplementedError()

    @contextlib.contextmanager
    def new_file(self, path: str, binary: bool = False):
        raise NotImplementedError()


# This is a prototype implementation. Chock full of races, and other
# problems
# Do not use in prod!
# local-artifact://[path][asdfdsa][asdf]
class LocalArtifact(Artifact):
    def __init__(self, name: str, version: typing.Optional[str] = None):
        self.name = name
        self._version = version
        self._root = os.path.join(local_artifact_dir(), name)
        self._path_handlers: dict[str, typing.Any] = {}
        os.makedirs(self._root, exist_ok=True)
        self._setup_dirs()

        pathlib.Path(os.path.join(self._root, ".wandb-artifact")).touch()

        self._last_write_path = None

    def __repr__(self):
        return "<LocalArtifact(%s) %s %s>" % (id(self), self.name, self._version)

    @property
    def is_saved(self) -> bool:
        return self._version is not None

    @property
    def version(self):
        if not self.is_saved:
            raise errors.WeaveInternalError(
                "artifact must be saved before calling version!"
            )
        return self._version

    @property
    def created_at(self):
        return self.read_metadata()["created_at"]

    def get_other_version(self, version: str) -> typing.Optional["LocalArtifact"]:
        if not local_artifact_exists(self.name, version):
            return None
        return LocalArtifact(self.name, version)

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

    def path(self, name):
        return os.path.join(self._read_dirname, name)

    @property
    def location(self) -> uris.WeaveURI:
        return uris.WeaveLocalArtifactURI.from_parts(
            os.path.abspath(local_artifact_dir()), self.name, self.version
        )

    def uri(self) -> str:
        return self.location.uri

    @contextlib.contextmanager
    def new_file(self, path, binary=False):
        self._last_write_path = path

        os.makedirs(self._write_dirname, exist_ok=True)
        mode = "w"
        if binary:
            mode = "wb"
        f = open(os.path.join(self._write_dirname, path), mode)
        yield f
        f.close()

    @contextlib.contextmanager
    def new_dir(self, path):
        full_path = os.path.abspath(os.path.join(self._write_dirname, path))
        os.makedirs(full_path, exist_ok=True)
        yield full_path

    def make_last_file_content_addressed(self):
        # Warning: This function is really bad and a terrible smell!
        # We need to fix the type saving API so we don't need to do this!!!!
        # It also causes double hashing.
        # TODO: fix
        # DO NOT MERGE
        last_write_path = self._last_write_path
        if last_write_path is None:
            return
        self._last_write_path = None
        orig_full_path = os.path.join(self._write_dirname, last_write_path)
        hash = md5_hash_file(orig_full_path)
        target_name = f"{hash}-{last_write_path}"
        os.rename(orig_full_path, os.path.join(self._write_dirname, target_name))
        return hash

    @contextlib.contextmanager
    def open(self, path, binary=False):
        mode = "r"
        if binary:
            mode = "rb"
        f = open(os.path.join(self._read_dirname, path), mode)
        yield f
        f.close()

    def get_path_handler(self, path, handler_constructor):
        handler = self._path_handlers.get(path)
        if handler is None:
            handler = handler_constructor(self, path)
            self._path_handlers[path] = handler
        return handler

    def read_metadata(self):
        with open(os.path.join(self._read_dirname, ".artifact-version.json")) as f:
            obj = json.load(f)
            obj["created_at"] = datetime.fromisoformat(obj["created_at"])
            return obj

    def write_metadata(self, dirname):
        with open(os.path.join(dirname, ".artifact-version.json"), "w") as f:
            json.dump({"created_at": datetime.now().isoformat()}, f)

    def save(self, branch="latest"):
        for handler in self._path_handlers.values():
            handler.close()
        self._path_handlers = {}
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
            self.write_metadata(new_dirname)
            if self._read_dirname:
                for path in os.listdir(self._read_dirname):
                    src_path = os.path.join(self._read_dirname, path)
                    target_path = os.path.join(new_dirname, path)
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, target_path)
                    else:
                        shutil.copyfile(src_path, target_path)
            for path in os.listdir(self._write_dirname):
                src_path = os.path.join(self._write_dirname, path)
                target_path = os.path.join(new_dirname, path)
                if os.path.isdir(src_path):
                    shutil.copytree(src_path, target_path)
                else:
                    shutil.copyfile(src_path, target_path)
        shutil.rmtree(self._write_dirname)
        self._setup_dirs()

        # Example of one of many races here
        # ensure tempdir root exists
        tmpdir_root = pathlib.Path(os.path.join(local_artifact_dir(), "tmp"))
        tmpdir_root.mkdir(exist_ok=True)

        link_name = os.path.join(self._root, branch)
        with tempfile.TemporaryDirectory(dir=tmpdir_root) as d:
            temp_path = os.path.join(d, "tmplink")
            os.symlink(self._version, temp_path)
            os.rename(temp_path, link_name)


class WandbArtifact(Artifact):
    def __init__(self, name, type=None, uri: uris.WeaveWBArtifactURI = None):
        self.name = name
        if not uri:
            self._writeable_artifact = wandb.Artifact(
                name, type="op_def" if type is None else type
            )
        else:
            # load an existing artifact, this should be read only,
            # TODO: we could technically support writable artifacts by creating a new version?
            self._saved_artifact = get_wandb_read_artifact(uri.make_path())
        self._local_path: dict[str, str] = {}

    def __repr__(self):
        return "<WandbArtifact %s>" % self.name

    @classmethod
    def from_wb_artifact(cls, art):
        uri = uris.WeaveWBArtifactURI.from_parts(
            art.entity,
            art.project,
            art._sequence_name,
            art.version,
        )
        return cls(art._sequence_name, uri=uri)

    def make_last_file_content_addressed(self):
        return None

    @property
    def is_saved(self) -> bool:
        return hasattr(self, "_saved_artifact")

    @property
    def version(self):
        if not self._saved_artifact:
            raise errors.WeaveInternalError("cannot get version of an unsaved artifact")
        return self._saved_artifact.version

    @property
    def created_at(self):
        raise NotImplementedError()

    def get_other_version(self, version):
        raise NotImplementedError()

    def path(self, name):
        # TODO: this is not thread safe if used with a shared filesystem, maybe we should use a local tmp dir?
        if not self._saved_artifact:
            raise errors.WeaveInternalError("cannot download of an unsaved artifact")
        if name in self._local_path:
            return self._local_path[name]
        if name not in self._saved_artifact.manifest.entries:
            found = False
            for entry in self._saved_artifact.manifest.entries:
                if entry.startswith(name):
                    _path = self.path(entry)
                    found = True
            if found:
                return os.path.join(self._saved_artifact._default_root(), name)
        path = self._saved_artifact.get_path(name).download()
        # python module loading does not support colons
        # TODO: This is an extremely expensive fix!
        path_safe = path.replace(":", "_")
        pathlib.Path(path_safe).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, path_safe)
        self._local_path[name] = path_safe
        return path_safe

    @property
    def location(self):
        return uris.WeaveWBArtifactURI.from_parts(
            self._saved_artifact.entity,
            self._saved_artifact.project,
            self.name,
            self._saved_artifact.version,
        )

    def uri(self) -> str:
        if not self._saved_artifact:
            raise errors.WeaveInternalError("cannot get uri of an unsaved artifact")
        # TODO: should we include server URL here?
        return self.location.uri

    @contextlib.contextmanager
    def new_file(self, path, binary=False):
        if not self._writeable_artifact:
            raise errors.WeaveInternalError("cannot add new file to readonly artifact")
        mode = "w"
        if binary:
            mode = "wb"
        with self._writeable_artifact.new_file(path, mode) as f:
            yield f

    @contextlib.contextmanager
    def new_dir(self, path):
        if not self._writeable_artifact:
            raise errors.WeaveInternalError("cannot add new file to readonly artifact")
        with tempfile.TemporaryDirectory() as tmpdir:
            yield os.path.abspath(tmpdir)
            self._writeable_artifact.add_dir(tmpdir, path)

    @contextlib.contextmanager
    def open(self, path, binary=False):
        if not self._saved_artifact:
            raise errors.WeaveInternalError("cannot load data from an unsaved artifact")
        mode = "r"
        if binary:
            mode = "rb"
        p = self.path(path)
        with open(p, mode) as f:
            yield f

    def get_path_handler(self, path, handler_constructor):
        raise NotImplementedError()

    def read_metadata(self):
        raise NotImplementedError()

    def write_metadata(self, dirname):
        raise NotImplementedError()

    def save(self, project: str = "weave_ops"):
        # TODO: technically save should be sufficient but we need the run to grab the entity name and project name
        # TODO: what project should we put weave ops in???
        os.environ["WANDB_SILENT"] = "true"
        wandb.require("service")  # speeds things up
        run = wandb.init(project=project)
        self._writeable_artifact.save()
        self._writeable_artifact.wait()
        run.finish()

        self._saved_artifact = wandb_api.wandb_public_api().artifact(
            f"{run.entity}/{project}/{self._writeable_artifact.name}"
        )
