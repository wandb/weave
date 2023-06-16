import contextlib
import dataclasses
import hashlib
import os
import json
import typing
import shutil
from datetime import datetime
import pathlib
import tempfile

from . import uris
from . import util
from . import errors

from . import weave_types as types
from . import artifact_wandb
from . import artifact_fs
from . import file_base
from . import file_util
from . import filesystem
from . import environment

WORKING_DIR_PREFIX = "__working__"


def local_artifact_dir() -> str:
    d = os.path.join(filesystem.get_filesystem_dir(), "local-artifacts")
    os.makedirs(d, exist_ok=True)
    return d


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


class LocalArtifactType(artifact_fs.FilesystemArtifactType):
    def save_instance(self, obj, artifact, name) -> "LocalArtifactRef":
        return LocalArtifactRef(obj, None)

    # No load_instance because we're returning a ref from save_instance.
    # Weave handles loading from that Ref automatically.


RESERVED_METADATA_KEYS = ["branch_point", "created_at", "previous_commit_uri"]


class LocalArtifact(artifact_fs.FilesystemArtifact):
    _existing_dirs: list[str]
    _original_uri: typing.Optional[str]
    _metadata: dict[str, typing.Any]

    def __init__(self, name: str, version: typing.Optional[str] = None):
        # LocalArtifacts are created frequently, sometimes in cases where
        # they will neither be read to or written to. The to_python path does
        # this, it creates an Artifact in case any of the objects in the tree
        # we're serializing are custom and therefore would need to write to
        # the artifact. But most times, there are no custom objects in the tree.
        #
        # So for performance, its important to not create the directory structure until
        # until we actually need to write to the artifact.
        if "/" in name or "\\" in name or ".." in name or ":" in name:
            raise ValueError('Artifact name cannot contain "/" or "\\" or ".." or ":"')
        self.name = name
        self._version = version
        self._branch: typing.Optional[str] = None
        self._root = os.path.join(local_artifact_dir(), name)
        self._original_uri = None
        self._path_handlers: dict[str, typing.Any] = {}
        self._existing_dirs = []
        self._metadata = {}
        self._setup_dirs()

    @classmethod
    def fork_from_uri(
        cls,
        source_uri: typing.Union[
            "WeaveLocalArtifactURI", artifact_wandb.WeaveWBArtifactURI
        ],
    ):
        art = cls(source_uri.name, source_uri.version)
        art._original_uri = str(source_uri)
        source_art = source_uri.to_ref().artifact
        if not isinstance(source_art, (LocalArtifact, artifact_wandb.WandbArtifact)):
            raise errors.WeaveInternalError(
                "Cannot fork from non-local artifact: %s" % source_art
            )
        art._version = source_art.version
        art._metadata = source_art.metadata.as_dict()
        return art

    # If an object has a _ref property, it will be used by ref_base._get_ref()
    @property
    def _ref(self) -> "LocalArtifactRef":
        if not self.is_saved:
            raise errors.WeaveInternalError("cannot get ref of an unsaved artifact")
        return LocalArtifactRef(self, None, None)

    def __repr__(self):
        return "<LocalArtifact(%s) %s %s>" % (id(self), self.name, self._version)

    def delete(self):
        shutil.rmtree(self._root)

    def rename(self, new_name: str):
        shutil.move(self._root, os.path.join(local_artifact_dir(), new_name))

    @property
    def is_saved(self) -> bool:
        return self._read_dirname is not None and self._version is not None

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

    @property
    def branch(self):
        return self._branch

    @property
    def branch_point(self) -> typing.Optional[artifact_fs.BranchPointType]:
        return self.read_metadata().get("branch_point")

    def previous_uri(self) -> typing.Optional[str]:
        previous_commit_uri = self.read_metadata().get("previous_commit_uri")
        if previous_commit_uri is not None:
            return previous_commit_uri

        branch_point = self.branch_point
        if branch_point is not None:
            original_uri = branch_point["original_uri"]
            return original_uri
        return None

    def undo(self) -> typing.Optional[artifact_fs.FilesystemArtifact]:
        # Fetch the previous uri (could be from a local commit or a branch)
        previous_uri = self.previous_uri()
        if previous_uri is None:
            return None

        # Should we delete the current version?
        # self.delete()

        # Make sure we're undoing to an artifact uri
        original_uri_obj = uris.WeaveURI.parse(previous_uri)
        if not isinstance(
            original_uri_obj, (artifact_wandb.WeaveWBArtifactURI, WeaveLocalArtifactURI)
        ):
            raise errors.WeaveInternalError(
                "Cannot undo to non artifact uri: %s" % previous_uri
            )

        # Get the previous version
        previous_version = original_uri_obj.to_ref().artifact

        # If we are currently on a branch, and our previous version is local, then
        # we want to manually update the branch to point to the previous version.
        branch_name = self.branch
        if branch_name != None and isinstance(previous_version, LocalArtifact):
            commit_hash = previous_version.version
            if commit_hash != None and artifact_wandb.likely_commit_hash(commit_hash):
                previous_version._branch = branch_name
                link_name = os.path.join(previous_version._root, branch_name)
                target_name = os.path.join(previous_version._root, commit_hash)
                safe_os_symlink(target_name, link_name)

        # Return the previous version
        return previous_version

    def get_other_version(self, version: str) -> typing.Optional["LocalArtifact"]:
        if not local_artifact_exists(self.name, version):
            return None
        return LocalArtifact(self.name, version)

    def _setup_dirs(self):
        # NOTE: do not write to the filesystem here! This is called to construct
        # an artifact that may not exist or ever be read or written to.
        self._write_dirname = os.path.join(
            self._root, f"{WORKING_DIR_PREFIX}-{util.rand_string_n(12)}"
        )
        self._read_dirname = None
        if self._version:
            read_dirname = os.path.join(self._root, self._version)
            if not os.path.exists(read_dirname):
                # If it doesn't exist, assume the user has passed in a branch name
                # for version.
                self._branch = self._version
            else:
                self._read_dirname = os.path.join(self._root, self._version)

                # if this is a branch, set to the actual specific version it points to
                if os.path.islink(self._read_dirname):
                    self._branch = self._version
                    self._version = os.path.basename(
                        os.path.realpath(self._read_dirname)
                    )
                    self._read_dirname = os.path.join(self._root, self._version)
        if self._branch != None:
            self._original_uri = str(
                WeaveLocalArtifactURI(
                    self.name,
                    self._branch,
                )
            )

    def _get_read_path(self, path: str) -> pathlib.Path:
        read_dirname = pathlib.Path(self._read_dirname)
        full_path = read_dirname / path
        if not pathlib.Path(full_path).resolve().is_relative_to(read_dirname.resolve()):
            raise errors.WeaveAccessDeniedError()
        return full_path

    def _get_write_path(self, path: str) -> pathlib.Path:
        write_dirname = pathlib.Path(self._write_dirname)
        full_path = write_dirname / path
        if (
            not pathlib.Path(full_path)
            .resolve()
            .is_relative_to(write_dirname.resolve())
        ):
            raise errors.WeaveAccessDeniedError()
        return full_path

    def direct_url(self, name: str) -> str:
        art_path = self.path(name)
        local_path = os.path.abspath(art_path)
        return f"{environment.weave_server_url()}/__weave/file{local_path}"

    def path(self, name: str) -> str:
        return str(self._get_read_path(name))

    @property
    def initial_uri_obj(self) -> uris.WeaveURI:
        version = self._branch or self._version
        if version is None:
            raise errors.WeaveInternalError("Cannot get uri for unsaved artifact!")
        return WeaveLocalArtifactURI(
            self.name,
            version,
        )

    @property
    def uri_obj(self) -> uris.WeaveURI:
        version = self._version
        if version is None:
            raise errors.WeaveInternalError("Cannot get uri for unsaved artifact!")
        return WeaveLocalArtifactURI(
            self.name,
            version,
        )

    def path_uri(self, path) -> uris.WeaveURI:
        version = self._version
        if version is None:
            raise errors.WeaveInternalError("Cannot get uri for unsaved artifact!")
        return WeaveLocalArtifactURI(
            self.name,
            self._version,
            path,
        )

    def _makedir(self, dirname: str):
        # Keep track of directories we've already created so we don't
        # create them multiple times, makedir is expensive if you call
        # it a million times, especially on a network file store!
        if dirname not in self._existing_dirs:
            os.makedirs(dirname, exist_ok=True)
            self._existing_dirs.append(dirname)

    @contextlib.contextmanager
    def new_file(self, path, binary=False):
        full_path = os.path.join(self._write_dirname, path)
        self._makedir(os.path.dirname(full_path))
        mode = "w"
        if binary:
            mode = "wb"
        f = file_util.safe_open(full_path, mode)
        yield f
        f.close()

    @contextlib.contextmanager
    def new_dir(self, path):
        full_path = self._get_write_path(path)
        self._makedir(full_path)
        os.makedirs(full_path, exist_ok=True)
        yield full_path

    @contextlib.contextmanager
    def open(self, path, binary=False):
        mode = "r"
        if binary:
            mode = "rb"
        f = file_util.safe_open(os.path.join(self._read_dirname, path), mode)
        yield f
        f.close()

    def get_path_handler(self, path, handler_constructor):
        handler = self._path_handlers.get(path)
        if handler is None:
            handler = handler_constructor(self, path)
            self._path_handlers[path] = handler
        return handler

    def read_metadata(self):
        if not self._read_dirname:
            return {}
        with file_util.safe_open(
            os.path.join(self._read_dirname, ".artifact-version.json")
        ) as f:
            obj = json.load(f)
            obj["created_at"] = datetime.fromisoformat(obj["created_at"])
            return obj

    def write_metadata(self, dirname, metadata):
        self._makedir(dirname)
        with file_util.safe_open(
            os.path.join(dirname, ".artifact-version.json"), "w"
        ) as f:
            json.dump({"created_at": datetime.now().isoformat(), **metadata}, f)

    def save(self, branch=None):
        for handler in self._path_handlers.values():
            handler.close()
        self._path_handlers = {}
        manifest = {}
        if self._read_dirname:
            for dirpath, dnames, fnames in os.walk(self._read_dirname):
                for f in fnames:
                    if f != ".artifact-version.json":
                        full_path = os.path.join(dirpath, f)
                        manifest[f] = md5_hash_file(full_path)
        for dirpath, dnames, fnames in os.walk(self._write_dirname):
            for f in fnames:
                if f != ".artifact-version.json":
                    full_path = os.path.join(dirpath, f)
                    manifest[f] = md5_hash_file(full_path)
        commit_hash = md5_string(json.dumps(manifest, sort_keys=True, indent=2))[
            : artifact_wandb.WANDB_COMMIT_HASH_LENGTH
        ]

        new_dirname = os.path.join(self._root, commit_hash)

        if not self._read_dirname:
            # we're not read-modify-writing an existing version, so
            # just rename the write dir
            try:
                os.rename(self._write_dirname, new_dirname)
            except OSError:
                # Someone already created this version.
                if os.path.exists(self._write_dirname):
                    shutil.rmtree(self._write_dirname)
        else:
            # read-modify-write of existing version, so copy existing
            # files into new dir first, then overwrite with new files

            # using a working directory so we can atomic rename at end
            tmpdir = os.path.join(self._root, "tmpwritedir-%s" % util.rand_string_n(12))
            os.makedirs(tmpdir, exist_ok=True)
            if self._read_dirname:
                for path in os.listdir(self._read_dirname):
                    src_path = os.path.join(self._read_dirname, path)
                    target_path = os.path.join(tmpdir, path)
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, target_path)
                    else:
                        shutil.copyfile(src_path, target_path)
            if os.path.exists(self._write_dirname):
                for path in os.listdir(self._write_dirname):
                    src_path = os.path.join(self._write_dirname, path)
                    target_path = os.path.join(tmpdir, path)
                    if os.path.isdir(src_path):
                        shutil.copytree(src_path, target_path, dirs_exist_ok=True)
                    else:
                        shutil.copyfile(src_path, target_path)
            try:
                os.rename(tmpdir, new_dirname)
            except OSError:
                shutil.rmtree(tmpdir)
            if os.path.exists(self._write_dirname):
                shutil.rmtree(self._write_dirname)

        if branch is None:
            branch = self._branch

        metadata = {**self.metadata.as_dict()}
        # I don't think we need to delete this, but doing so
        # to be safe
        last_previous_uri = None
        for key in RESERVED_METADATA_KEYS:
            if key in metadata:
                if key == "previous_commit_uri":
                    last_previous_uri = metadata[key]
                del metadata[key]
        if self._original_uri != None and (
            branch != self._branch or self._original_uri.startswith("wandb-artifact://")
        ):
            # new branch
            metadata["branch_point"] = {
                "original_uri": self._original_uri,
                "commit": self._version,
                "n_commits": 1,
            }
        else:
            # same branch, same branch point
            if self.branch_point:
                metadata["branch_point"] = self.branch_point
                metadata["branch_point"]["n_commits"] += 1
        if (
            self.is_saved
            and self.version
            and artifact_wandb.likely_commit_hash(self.version)
            and self.version != commit_hash
        ):
            metadata["previous_commit_uri"] = str(self.uri_obj)
        elif last_previous_uri != None:
            # TODO: Refactor this to be more sane - we should be explicit about
            # what metadata carries over and protect against duplicate saves
            metadata["previous_commit_uri"] = last_previous_uri
        self.write_metadata(new_dirname, metadata)

        self._version = commit_hash
        self._setup_dirs()

        def make_link(dirname: str):
            link_name = os.path.join(self._root, dirname)
            safe_os_symlink(commit_hash, link_name)

        if branch is not None:
            self._branch = branch
            make_link(branch)
        else:
            make_link("latest")

    def _path_info(
        self, path: str
    ) -> typing.Optional[
        typing.Union[
            "artifact_fs.FilesystemArtifactFile", "artifact_fs.FilesystemArtifactDir"
        ]
    ]:
        read_dirname = pathlib.Path(self._read_dirname)
        local_path = self._get_read_path(path)
        if local_path.is_file():
            return artifact_fs.FilesystemArtifactFile(self, path)
        elif local_path.is_dir():
            sub_files = {}
            sub_dirs = {}
            for sub_path in local_path.iterdir():
                relpath = str(sub_path.relative_to(read_dirname))
                if relpath == ".artifact-version.json":
                    continue
                if sub_path.is_file():
                    sub_files[sub_path.name] = artifact_fs.FilesystemArtifactFile(
                        self, relpath
                    )
                else:
                    sub_dirs[sub_path.name] = file_base.SubDir(
                        relpath,
                        25,  # TODO: size
                        {},
                        {},
                    )
            return artifact_fs.FilesystemArtifactDir(
                self, path, 14, sub_dirs, sub_files
            )
        else:
            return None

    @property
    def metadata(self) -> artifact_fs.ArtifactMetadata:
        read_metadata = {
            k: v
            for k, v in self.read_metadata().items()
            if k not in RESERVED_METADATA_KEYS
        }
        return artifact_fs.ArtifactMetadata(self._metadata, read_metadata)


def safe_os_symlink(target_path: str, symlink_path: str):
    # Example of one of many races here
    # ensure tempdir root exists
    tmpdir_root = pathlib.Path(os.path.join(local_artifact_dir(), "tmp"))
    tmpdir_root.mkdir(exist_ok=True)
    tmp_path_name = f"tmplink-{util.rand_string_n(12)}"
    with tempfile.TemporaryDirectory(dir=tmpdir_root) as d:
        temp_path = os.path.join(d, tmp_path_name)
        os.symlink(target_path, temp_path)
        os.rename(temp_path, symlink_path)


LocalArtifactType.instance_classes = LocalArtifact


class LocalArtifactRef(artifact_fs.FilesystemArtifactRef):
    artifact: LocalArtifact

    def versions(self) -> list[artifact_fs.FilesystemArtifactRef]:
        artifact_path = os.path.join(local_artifact_dir(), self.artifact.name)
        versions = []
        for version_name in os.listdir(artifact_path):
            if (
                not os.path.islink(os.path.join(artifact_path, version_name))
                and not version_name.startswith(WORKING_DIR_PREFIX)
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
                ref = LocalArtifactRef(art, path="obj")
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
            LocalArtifact(uri.name, uri.version),
            path=uri.path,
            obj=None,
            extra=uri.extra,
        )


types.LocalArtifactRefType.instance_class = LocalArtifactRef
types.LocalArtifactRefType.instance_classes = LocalArtifactRef

LocalArtifact.RefClass = LocalArtifactRef


@dataclasses.dataclass
class WeaveLocalArtifactURI(uris.WeaveURI):
    SCHEME = "local-artifact"
    path: typing.Optional[str] = None
    extra: typing.Optional[list[str]] = None

    @classmethod
    def from_parsed_uri(
        cls,
        uri: str,
        schema: str,
        netloc: str,
        path: str,
        params: str,
        query: dict[str, list[str]],
        fragment: str,
    ):
        parts = path.strip("/").split("/")
        name, version = parts[0].split(":", 1)
        file_path: typing.Optional[str] = None
        if len(parts) > 1:
            file_path = "/".join(parts[1:])
        extra: typing.Optional[list[str]] = None
        if fragment:
            extra = fragment.split("/")
        return cls(name, version, file_path, extra)

    def __str__(self) -> str:
        uri = f"{self.SCHEME}:///{self.name}:{self.version}"
        if self.path:
            uri += f"/{self.path}"
        if self.extra:
            uri += f"#{'/'.join(self.extra)}"
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
    return LocalArtifactRef(art, path="obj")


# Should probably be "get_version_object()"
def get_local_version(name: str, version: str) -> typing.Any:
    ref = get_local_version_ref(name, version)
    if ref is None:
        return None
    return ref.get()
