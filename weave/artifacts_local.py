import contextlib
import hashlib
import os
import pathlib
import json
import shutil
from datetime import datetime

from . import util


LOCAL_ARTIFACT_DIR = os.environ.get("WEAVE_LOCAL_ARTIFACT_DIR") or os.path.join(
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


def local_artifact_exists(name, branch):
    return os.path.exists(os.path.join(LOCAL_ARTIFACT_DIR, name, branch))


# This is a prototype implementation. Chock full of races, and other
# problems
# Do not use in prod!
class LocalArtifact:
    def __init__(self, name, version=None):
        self._name = name
        self._version = version
        self._root = os.path.join(LOCAL_ARTIFACT_DIR, name)
        self._path_handlers = {}
        os.makedirs(self._root, exist_ok=True)
        self._setup_dirs()

        pathlib.Path(os.path.join(self._root, ".wandb-artifact")).touch()

        self._last_write_path = None

    def __repr__(self):
        return "<LocalArtifact(%s) %s %s>" % (id(self), self._name, self._version)

    @property
    def version(self):
        if self._version is None:
            raise Exception("artifact must be saved before calling version!")
        return self._version

    @property
    def created_at(self):
        return self.read_metadata()["created_at"]

    def get_other_version(self, version):
        if not local_artifact_exists(self._name, version):
            return None
        return LocalArtifact(self._name, version)

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
