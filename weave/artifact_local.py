import contextlib
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

from . import weave_types as types
from . import ref_artifact
from . import artifact_base
from . import artifact_util


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
    return os.path.exists(
        os.path.join(artifact_util.local_artifact_dir(), name, branch)
    )


class LocalArtifact(artifact_base.Artifact):
    def __init__(self, name: str, version: typing.Optional[str] = None):
        # LocalArtifacts are created frequently, sometimes in cases where
        # they will neither be read to or written to. The to_python path does
        # this, it creates an Artifact in case any of the objects in the tree
        # we're serializing are custom and therefore would need to write to
        # the artifact. But most times, there are no custom objects in the tree.
        #
        # So for performance, its important to not create the directory structure until
        # until we actually need to write to the artifact.
        self.name = name
        self._version = version
        self._root = os.path.join(artifact_util.local_artifact_dir(), name)
        self._path_handlers: dict[str, typing.Any] = {}
        self._setup_dirs()
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

    def path(self, name: str) -> str:
        return os.path.join(self._read_dirname, name)

    @property
    def location(self) -> uris.WeaveURI:
        return WeaveLocalArtifactURI.from_parts(
            os.path.abspath(artifact_util.local_artifact_dir()), self.name, self.version
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
            shutil.rmtree(self._write_dirname)
        else:
            new_dirname = os.path.join(self._root, commit_hash)
            if not self._read_dirname:
                # we're not read-modify-writing an existing version, so
                # just rename the write dir
                os.rename(self._write_dirname, new_dirname)
                self.write_metadata(new_dirname)
            else:
                # read-modify-write of existing version, so copy existing
                # files into new dir first, then overwrite with new files
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
        tmpdir_root = pathlib.Path(
            os.path.join(artifact_util.local_artifact_dir(), "tmp")
        )
        tmpdir_root.mkdir(exist_ok=True)

        link_name = os.path.join(self._root, branch)
        with tempfile.TemporaryDirectory(dir=tmpdir_root) as d:
            temp_path = os.path.join(d, "tmplink")
            os.symlink(self._version, temp_path)
            os.rename(temp_path, link_name)


class LocalArtifactRef(ref_artifact.ArtifactRef):
    FileType = types.FileType

    artifact: LocalArtifact

    def versions(self) -> list[ref_artifact.ArtifactRef]:
        artifact_path = os.path.join(
            artifact_util.local_artifact_dir(), self.artifact.name
        )
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
                art = self.artifact.get_other_version(version_name)
                if art is None:
                    raise errors.WeaveInternalError(
                        "Could not get other version: %s %s"
                        % (self.artifact, version_name)
                    )
                ref = LocalArtifactRef(art, path="_obj")
                # obj = uri.get()
                # ref = get_ref(obj)
                versions.append(ref)
        return sorted(versions, key=lambda v: v.artifact.created_at)

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "LocalArtifactRef":
        if not isinstance(uri, WeaveLocalArtifactURI):
            raise errors.WeaveInternalError(
                f"Invalid URI class passed to WandbLocalArtifactRef.from_uri: {type(uri)}"
            )
        return cls(
            LocalArtifact(uri.full_name, uri.version),
            path=uri.file,
            obj=None,
            extra=uri.extra,
        )


types.LocalArtifactRefType.instance_class = LocalArtifactRef
types.LocalArtifactRefType.instance_classes = LocalArtifactRef

LocalArtifact.RefClass = LocalArtifactRef


# Used when the Weave object is located on disk (eg after saving locally).
#
# Note: this can change over time as it is only used in-process
# local-artifact://user/timothysweeney/workspace/.../local-artifacts/<friendly_name>/<version>?extra=<extra_parts>
class WeaveLocalArtifactURI(uris.WeaveURI):
    scheme = "local-artifact"

    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        parts = self.path.split("/")
        if len(parts) < 2:
            raise errors.WeaveInternalError("invalid uri ", uri)
        self._full_name = parts[-2]
        self._version = parts[-1]

    @classmethod
    def from_parts(
        cls: typing.Type["WeaveLocalArtifactURI"],
        root: str,
        friendly_name: str,
        version: typing.Optional[str] = None,
        extra: typing.Optional[list[str]] = None,
        file: typing.Optional[str] = None,
    ) -> "WeaveLocalArtifactURI":
        return cls(cls.make_uri(root, friendly_name, version, extra, file))

    @staticmethod
    def make_uri(
        root: str,
        friendly_name: str,
        version: typing.Optional[str] = None,
        extra: typing.Optional[list[str]] = None,
        file: typing.Optional[str] = None,
    ) -> str:
        uri = WeaveLocalArtifactURI.scheme + "://" + root + "/" + friendly_name
        if version is not None:
            uri += "/" + version

        uri = uri + uris.WeaveURI._generate_query_str(extra, file)
        return uri

    def to_ref(self) -> LocalArtifactRef:
        return LocalArtifactRef.from_uri(self)


def get_local_version_ref(name: str, version: str) -> typing.Optional[LocalArtifactRef]:
    # TODO: Watch out, this is a major race!
    #   - We need to eliminate this race or allow duplicate objectcs in parallel
    #     and then resolve later.
    #   - This is especially a problem for creating Runs and async Runs. We may
    #     accidentally launch parallel runs with the same run ID!
    if not local_artifact_exists(name, version):
        return None
    art = LocalArtifact(name, version)
    return LocalArtifactRef(art, path="_obj")


# Should probably be "get_version_object()"
def get_local_version(name: str, version: str) -> typing.Any:
    ref = get_local_version_ref(name, version)
    if ref is None:
        return None
    return ref.get()
