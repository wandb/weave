import contextlib
import functools
import hashlib
import os
import json
import random
import shutil
from datetime import datetime
import pathlib
import tempfile
import typing

from . import uris
from . import util
from . import errors
from . import wandb_api
from . import context_state
from . import memo

import wandb
from wandb.apis import public as wb_public
from wandb.util import hex_to_b64_id


def local_artifact_dir() -> str:
    # This is a directory that all local and wandb artifacts are stored within.
    # It includes the current cache namespace, which is a safe token per user,
    # to ensure cache separation.
    d = os.environ.get("WEAVE_LOCAL_ARTIFACT_DIR") or os.path.join(
        "/tmp", "local-artifacts"
    )
    cache_namespace = context_state._cache_namespace_token.get()
    if cache_namespace:
        d = os.path.join(d, cache_namespace)
    os.makedirs(d, exist_ok=True)
    return d


@memo.memo
def get_wandb_read_artifact(path):
    return wandb_api.wandb_public_api().artifact(path)


@memo.memo
def get_wandb_read_run(path):
    return wandb_api.wandb_public_api().run(path)


@memo.memo
def get_wandb_read_client_artifact(art_id: str):
    """art_id may be client_id, or seq:alias"""
    if ":" in art_id:
        art_id, art_version = art_id.split(":")
        query = wb_public.gql(
            """	
        query ArtifactVersionFromIdAlias(	
            $id: ID!,	
            $aliasName: String!	
        ) {	
            artifactCollection(id: $id) {	
                id	
                name	
                project {	
                    id	
                    name	
                    entity {	
                        id	
                        name	
                    }	
                }	
                artifactMembership(aliasName: $aliasName) {	
                    id	
                    versionIndex	
                }	
                defaultArtifactType {	
                    id	
                    name	
                }	
            }	
        }	
        """
        )
        res = wandb_api.wandb_public_api().client.execute(
            query,
            variable_values={
                "id": art_id,
                "aliasName": art_version,
            },
        )
        collection = res["artifactCollection"]
        artifact_type_name = res["artifactCollection"]["defaultArtifactType"]["name"]
        version_index = res["artifactCollection"]["artifactMembership"]["versionIndex"]
    else:
        query = wb_public.gql(
            """	
        query ArtifactVersionFromClientId(	
            $id: ID!,	
        ) {	
            artifact(id: $id) {	
                id
                versionIndex
                artifactType {	
                    id	
                    name	
                }	
                artifactSequence {
                    id
                    name
                    project {
                        id
                        name
                        entity {
                            id
                            name
                        }
                    }
                }
            }	
        }	
        """
        )
        res = wandb_api.wandb_public_api().client.execute(
            query,
            variable_values={"id": hex_to_b64_id(art_id)},
        )
        collection = res["artifact"]["artifactSequence"]
        artifact_type_name = res["artifact"]["artifactType"]["name"]
        version_index = res["artifact"]["versionIndex"]

    entity_name = collection["project"]["entity"]["name"]
    project_name = collection["project"]["name"]
    artifact_name = collection["name"]
    version = f"v{version_index}"

    for var_name, var_val in [
        ("entity_name", entity_name),
        ("project_name", project_name),
        ("artifact_type_name", artifact_type_name),
        ("artifact_name", artifact_name),
        ("version_index", version_index),
    ]:
        if var_val is None or var_val == "":
            raise errors.WeaveClientArtifactResolutionFailure(
                f"Failed to resolve {var_name} for {art_id}. Have {res}."
            )

    weave_art_uri = uris.WeaveWBArtifactURI.from_parts(
        entity_name,
        project_name,
        artifact_name,
        version,
    )
    return WandbArtifact(artifact_name, artifact_type_name, weave_art_uri)


@contextlib.contextmanager
def _isolated_download_and_atomic_mover(
    end_path: str,
) -> typing.Generator[typing.Tuple[str, typing.Callable[[str], None]], None, None]:
    rand_part = "".join(random.choice("0123456789ABCDEF") for _ in range(16))
    tmp_dir = os.path.join(local_artifact_dir(), f"tmp_{rand_part}")
    os.makedirs(tmp_dir, exist_ok=True)

    def mover(tmp_path: str):
        # This uses the same technique as WB artifacts
        pathlib.Path(end_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(tmp_path, end_path)
        except AttributeError:
            os.rename(tmp_path, end_path)

    try:
        yield tmp_dir, mover
    finally:
        shutil.rmtree(tmp_dir)


def wandb_artifact_dir():
    # Make this a subdir of local_artifact_dir, since the server
    # checks for local_artifact_dir to see if it should serve
    d = os.path.join(local_artifact_dir(), "_wandb_artifacts")
    os.makedirs(d, exist_ok=True)
    return d


def wandb_run_dir():
    d = os.path.join(local_artifact_dir(), "_wandb_runs")
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


class LocalArtifact(Artifact):
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
        self._root = os.path.join(local_artifact_dir(), name)
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
        tmpdir_root = pathlib.Path(os.path.join(local_artifact_dir(), "tmp"))
        tmpdir_root.mkdir(exist_ok=True)

        link_name = os.path.join(self._root, branch)
        with tempfile.TemporaryDirectory(dir=tmpdir_root) as d:
            temp_path = os.path.join(d, "tmplink")
            os.symlink(self._version, temp_path)
            os.rename(temp_path, link_name)


class WandbArtifact(Artifact):
    def __init__(
        self, name, type=None, uri: typing.Optional[uris.WeaveWBArtifactURI] = None
    ):
        self.name = name
        self._read_artifact_uri = None
        self._read_artifact = None
        if not uri:
            self._writeable_artifact = wandb.Artifact(
                name, type="op_def" if type is None else type
            )
        else:
            # load an existing artifact, this should be read only,
            # TODO: we could technically support writable artifacts by creating a new version?
            self._read_artifact_uri = uri
            # self._saved_artifact = get_wandb_read_artifact(uri.make_path())
        self._local_path: dict[str, str] = {}

    def _set_read_artifact_uri(self, uri):
        self._read_artifact = None
        self._read_artifact_uri = uri

    @property
    def _saved_artifact(self):
        if self._read_artifact is None:
            self._read_artifact = get_wandb_read_artifact(
                self._read_artifact_uri.make_path()
            )
        return self._read_artifact

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
        return self._read_artifact_uri is not None or self._read_artifact is not None

    @property
    def version(self):
        if not self.is_saved:
            raise errors.WeaveInternalError("cannot get version of an unsaved artifact")
        return self._saved_artifact.version

    @property
    def created_at(self):
        raise NotImplementedError()

    def get_other_version(self, version):
        raise NotImplementedError()

    def path(self, name):
        if not self.is_saved:
            raise errors.WeaveInternalError("cannot download of an unsaved artifact")

        # First, check if we already downloaded this file:
        if name in self._local_path:
            return self._local_path[name]

        # Next, we special case when the user is looking for a file
        # without the .[type].json extension. This is used for tables.
        if name not in self._saved_artifact.manifest.entries:
            for entry in self._saved_artifact.manifest.entries:
                if entry.startswith(name + ".") and entry.endswith(".json"):
                    self._local_path[name] = self.path(entry)
                    return self._local_path[name]

        # Generate the permanent path for this file:
        # Here, we include the ID as names might not be unique across all entities/projects
        # it would be nice to use entity/project name, but that is not available in the artifact
        # when constructed from ID (todo: update wandb sdk to support this)
        # python module loading does not support colons
        # TODO: This is an extremely expensive fix!
        static_file_path = os.path.join(
            wandb_artifact_dir(),
            "artifacts",
            f"{self._saved_artifact.name}_{self._saved_artifact.id}",
            name,
        ).replace(":", "_")

        # Next, check if another process has already downloaded this file:
        if os.path.exists(static_file_path):
            self._local_path[name] = static_file_path
            return static_file_path

        # Finally, download the file in an isolated directory:
        with _isolated_download_and_atomic_mover(static_file_path) as (tmp_dir, mover):
            downloaded_file_path = self._saved_artifact.get_path(name).download(tmp_dir)
            mover(downloaded_file_path)

        self._local_path[name] = static_file_path
        return static_file_path

    @property
    def location(self):
        return self._read_artifact_uri

    def uri(self) -> str:
        if not self.is_saved:
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
        if not self.is_saved:
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
        if run is None:
            raise errors.WeaveInternalError("unexpected, run is None")
        self._writeable_artifact.save()
        self._writeable_artifact.wait()
        run.finish()

        a_name, a_version = self._writeable_artifact.name.split(":")
        uri = uris.WeaveWBArtifactURI.from_parts(run.entity, project, a_name, a_version)
        self._set_read_artifact_uri(uri)


class WandbRunFilesProxyArtifact(Artifact):
    def __init__(self, entity_name: str, project_name: str, run_name: str):
        self.name = f"{entity_name}/{project_name}/{run_name}"
        self._run = get_wandb_read_run(self.name)
        self._local_path: dict[str, str] = {}

    @property
    def is_saved(self) -> bool:
        return True

    def path(self, name):
        # First, check if we already downloaded this file:
        if name in self._local_path:
            return self._local_path[name]

        static_file_path = os.path.join(wandb_run_dir(), str(self.name), name)
        # Next, check if another process has already downloaded this file:
        if os.path.exists(static_file_path):
            self._local_path[name] = static_file_path
            return static_file_path

        # Finally, download the file in an isolated directory:
        with _isolated_download_and_atomic_mover(static_file_path) as (tmp_dir, mover):
            with self._run.file(name).download(tmp_dir, replace=True) as fp:
                downloaded_file_path = fp.name
            mover(downloaded_file_path)

        self._local_path[name] = static_file_path
        return static_file_path
