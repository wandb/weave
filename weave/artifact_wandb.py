import binascii
import contextlib
import dataclasses
import os
import random
import shutil
import pathlib
import tempfile
import typing

import wandb
from wandb.apis import public as wb_public
from wandb.util import hex_to_b64_id, b64_to_hex_id

from . import uris
from . import errors
from . import wandb_client_api
from . import memo
from . import file_base
from . import file_util

from . import weave_types as types
from . import artifact_fs
from . import artifact_util

from urllib import parse


# TODO: Get rid of this, we have the new wandb api service! But this
# is still used in a couple places.
@memo.memo
def get_wandb_read_artifact(path: str):
    return wandb_client_api.wandb_public_api().artifact(path)


@memo.memo
def get_wandb_read_run(path):
    return wandb_client_api.wandb_public_api().run(path)


def wandb_artifact_dir():
    # Make this a subdir of local_artifact_dir, since the server
    # checks for local_artifact_dir to see if it should serve
    d = os.path.join(artifact_util.local_artifact_dir(), "_wandb_artifacts")
    os.makedirs(d, exist_ok=True)
    return d


def wandb_run_dir():
    d = os.path.join(artifact_util.local_artifact_dir(), "_wandb_runs")
    os.makedirs(d, exist_ok=True)
    return d


@memo.memo
def get_wandb_read_client_artifact_uri(art_id: str):
    """art_id may be client_id, seq:alias, or server_id"""
    # For joined or partioned tables it's unfortunately possible that
    # we need to exchange our client_id for a server_id.

    if len(art_id) == 128 and ":" not in art_id:
        query = wb_public.gql(
            """
            query ClientIDMapping($clientID: ID!) {
                clientIDMapping(clientID: $clientID) {
                    serverID
                }
            }
        """
        )
        res = wandb_client_api.wandb_public_api().client.execute(
            query,
            variable_values={
                "clientID": art_id,
            },
        )
        art_id = b64_to_hex_id(res["clientIDMapping"]["serverID"])

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
        res = wandb_client_api.wandb_public_api().client.execute(
            query,
            variable_values={
                "id": art_id,
                "aliasName": art_version,
            },
        )
        collection = res["artifactCollection"]
        artifact_type_name = res["artifactCollection"]["defaultArtifactType"]["name"]
        artifact_membership = res["artifactCollection"]["artifactMembership"]
        if artifact_membership is not None:
            version_index = artifact_membership["versionIndex"]
        else:
            version_index = None
    else:
        query = wb_public.gql(
            """	
        query ArtifactVersionFromServerId(	
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
        res = wandb_client_api.wandb_public_api().client.execute(
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

    weave_art_uri = WeaveWBArtifactURI(
        artifact_name,
        version,
        entity_name,
        project_name,
    )

    return weave_art_uri, artifact_type_name


def get_wandb_read_client_artifact(art_id: str) -> "WandbArtifact":
    """art_id may be client_id, seq:alias, or server_id"""
    weave_art_uri, artifact_type_name = get_wandb_read_client_artifact_uri(art_id)
    return WandbArtifact(weave_art_uri.name, artifact_type_name, weave_art_uri)


@contextlib.contextmanager
def _isolated_download_and_atomic_mover(
    end_path: str,
) -> typing.Generator[typing.Tuple[str, typing.Callable[[str], None]], None, None]:
    rand_part = "".join(random.choice("0123456789ABCDEF") for _ in range(16))
    tmp_dir = os.path.join(artifact_util.local_artifact_dir(), f"tmp_{rand_part}")
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


class WandbArtifactType(artifact_fs.FilesystemArtifactType):
    def save_instance(self, obj, artifact, name) -> "WandbArtifactRef":
        return WandbArtifactRef(obj, None)


class WandbArtifact(artifact_fs.FilesystemArtifact):
    def __init__(
        self,
        name,
        type=None,
        uri: typing.Optional[
            typing.Union["WeaveWBArtifactURI", "WeaveWBLoggedArtifactURI"]
        ] = None,
    ):
        from . import io_service

        self.sync_client = io_service.get_sync_client()
        self.name = name
        self._read_artifact_uri_or_client_uri = None
        self._read_artifact = None
        if not uri:
            self._writeable_artifact = wandb.Artifact(
                name, type="op_def" if type is None else type
            )
        else:
            # load an existing artifact, this should be read only,
            # TODO: we could technically support writable artifacts by creating a new version?
            self._read_artifact_uri_or_client_uri = uri
        self._local_path: dict[str, str] = {}

    @property
    def _read_artifact_uri(self) -> typing.Optional["WeaveWBArtifactURI"]:
        if isinstance(self._read_artifact_uri_or_client_uri, WeaveWBLoggedArtifactURI):
            self._read_artifact_uri_or_client_uri = (
                self._read_artifact_uri_or_client_uri.wb_artifact_uri
            )
        return self._read_artifact_uri_or_client_uri

    @property
    def _ref(self) -> "WandbArtifactRef":
        # existing_ref = ref_base.get_ref(obj)
        # if isinstance(existing_ref, artifact_base.ArtifactRef):
        #     return existing_ref
        if not self.is_saved:
            raise errors.WeaveInternalError("cannot get ref of an unsaved artifact")
        return WandbArtifactRef(self, None, None)

    def _set_read_artifact_uri(self, uri):
        self._read_artifact = None
        self._read_artifact_uri_or_client_uri = uri

    # TODO: still using wandb lib for this, but we should switch to the new
    # wandb api service
    @property
    def _saved_artifact(self):
        if self._read_artifact is None:
            uri = self._read_artifact_uri
            path = f"{uri.entity_name}/{uri.project_name}/{uri.name}:{uri.version}"
            self._read_artifact = get_wandb_read_artifact(path)
        return self._read_artifact

    def __repr__(self):
        return "<WandbArtifact %s>" % self.name

    @property
    def is_saved(self) -> bool:
        return (
            self._read_artifact_uri_or_client_uri is not None
            or self._read_artifact is not None
        )

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

    def path(self, name: str) -> str:
        if not self.is_saved or not self._read_artifact_uri:
            raise errors.WeaveInternalError("cannot download of an unsaved artifact")

        uri = self._read_artifact_uri.with_path(name)
        fs_path = self.sync_client.ensure_file(uri)
        if fs_path is None:
            raise errors.WeaveInternalError("Path not in artifact")
        return self.sync_client.fs.path(fs_path)

    def size(self, path: str) -> int:
        if path in self._saved_artifact.manifest.entries:
            return self._saved_artifact.manifest.entries[path].size
        return super().size(path)

    @property
    def uri_obj(self) -> typing.Union["WeaveWBArtifactURI", "WeaveWBLoggedArtifactURI"]:
        if not self.is_saved or not self._read_artifact_uri_or_client_uri:
            raise errors.WeaveInternalError("cannot get uri of an unsaved artifact")
        return self._read_artifact_uri_or_client_uri

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
        with file_util.safe_open(p, mode) as f:
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
        uri = WeaveWBArtifactURI(a_name, a_version, run.entity, project)
        self._set_read_artifact_uri(uri)

    def _path_info(
        self, path: str
    ) -> typing.Optional[
        typing.Union[
            "artifact_fs.FilesystemArtifactFile",
            "artifact_fs.FilesystemArtifactDir",
            "artifact_fs.FilesystemArtifactRef",
        ]
    ]:
        if self._read_artifact_uri is None:
            raise errors.WeaveInternalError(
                'cannot get path info for unsaved artifact"'
            )
        uri = self._read_artifact_uri.with_path(path)
        manifest = self.sync_client.manifest(uri)
        if manifest is None:
            return None
        manifest_entry = manifest.get_entry_by_path(path)
        if manifest_entry is not None:
            # This is not a WeaveURI! Its the artifact reference style used
            # by the W&B Artifacts/media layer.
            ref_prefix = "wandb-artifact://"
            if manifest_entry.ref and manifest_entry.ref.startswith(ref_prefix):
                # This is a reference to another artifact
                art_id, target_path = manifest_entry.ref[len(ref_prefix) :].split(
                    "/", 1
                )
                return artifact_fs.FilesystemArtifactFile(
                    get_wandb_read_client_artifact(art_id), target_path
                )
            # This is a file
            return artifact_fs.FilesystemArtifactFile(self, path)

        # This is not a file, assume its a directory. If not, we'll return an empty result.
        cur_dir = (
            path  # give better name so the rest of this code block is more readable
        )
        if cur_dir == "":
            dir_ents = manifest.entries.values()
        else:
            dir_ents = manifest.get_entries_in_directory(cur_dir)
        sub_dirs: dict[str, file_base.SubDir] = {}
        files = {}
        for entry in dir_ents:
            entry_path = entry.path
            rel_path = os.path.relpath(entry_path, path)
            rel_path_parts = rel_path.split("/")
            if len(rel_path_parts) == 1:
                files[rel_path_parts[0]] = artifact_fs.FilesystemArtifactFile(
                    self,
                    entry_path,
                )
            else:
                dir_name = rel_path_parts[0]
                if dir_name not in sub_dirs:
                    dir_ = file_base.SubDir(entry_path, 1111, {}, {})
                    sub_dirs[dir_name] = dir_
                dir_ = sub_dirs[dir_name]
                if len(rel_path_parts) == 2:
                    dir_files = typing.cast(dict, dir_.files)
                    dir_files[rel_path_parts[1]] = artifact_fs.FilesystemArtifactFile(
                        self,
                        entry_path,
                    )
                else:
                    dir_.dirs[rel_path_parts[1]] = 1
        if not sub_dirs and not files:
            return None
        return artifact_fs.FilesystemArtifactDir(self, path, 1591, sub_dirs, files)


WandbArtifactType.instance_classes = WandbArtifact


# TODO: Switch to new wandb api service
class WandbRunFilesProxyArtifact(artifact_fs.FilesystemArtifact):
    def __init__(self, entity_name: str, project_name: str, run_name: str):
        self.name = f"{entity_name}/{project_name}/{run_name}"
        self._local_path: dict[str, str] = {}
        self._run = None

    @property
    def is_saved(self) -> bool:
        return True

    @property
    def run(self):
        if self._run is None:
            self._run = get_wandb_read_run(self.name)
        return self._run

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
            with self.run.file(name).download(tmp_dir, replace=True) as fp:
                downloaded_file_path = fp.name
            mover(downloaded_file_path)

        self._local_path[name] = static_file_path
        return static_file_path


class WandbArtifactRef(artifact_fs.FilesystemArtifactRef):
    artifact: WandbArtifact

    def versions(self) -> list[artifact_fs.FilesystemArtifactRef]:
        # TODO: implement versions on wandb artifact
        return [self]

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "WandbArtifactRef":
        if not isinstance(uri, (WeaveWBArtifactURI, WeaveWBLoggedArtifactURI)):
            raise errors.WeaveInternalError(
                f"Invalid URI class passed to WandbArtifactRef.from_uri: {type(uri)}"
            )
        # TODO: potentially need to pass full entity/project/name instead
        return cls(
            WandbArtifact(uri.name, uri=uri),
            path=uri.path,
        )


types.WandbArtifactRefType.instance_class = WandbArtifactRef
types.WandbArtifactRefType.instance_classes = WandbArtifactRef

WandbArtifact.RefClass = WandbArtifactRef

# Used to refer to objects stored in WB Artifacts. This URI must not change and
# matches the existing artifact schemes
@dataclasses.dataclass
class WeaveWBArtifactURI(uris.WeaveURI):
    SCHEME = "wandb-artifact"
    entity_name: str
    project_name: str
    netloc: typing.Optional[str] = None
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
        if len(parts) < 3:
            raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")
        entity_name = parts[0]
        project_name = parts[1]
        name, version = parts[2].split(":", 1)
        file_path: typing.Optional[str] = None
        if len(parts) > 3:
            file_path = "/".join(parts[3:])
        extra: typing.Optional[list[str]] = None
        if fragment:
            extra = fragment.split("/")
        return cls(name, version, entity_name, project_name, netloc, file_path, extra)

    @classmethod
    def parse(cls: typing.Type["WeaveWBArtifactURI"], uri: str) -> "WeaveWBArtifactURI":
        return super().parse(uri)  # type: ignore

    def __str__(self) -> str:
        netloc = self.netloc or ""
        uri = f"{self.SCHEME}://{netloc}/{self.entity_name}/{self.project_name}/{self.name}:{self.version}"
        if self.path:
            uri += f"/{self.path}"
        if self.extra:
            uri += f"#{'/'.join(self.extra)}"
        return uri

    def with_path(self, path: str) -> "WeaveWBArtifactURI":
        return WeaveWBArtifactURI(
            self.name,
            self.version,
            self.entity_name,
            self.project_name,
            self.netloc,
            path,
            self.extra,
        )

    def to_ref(self) -> WandbArtifactRef:
        return WandbArtifactRef.from_uri(self)


@dataclasses.dataclass
class WeaveWBLoggedArtifactURI(uris.WeaveURI):
    SCHEME = "wandb-logged-artifact"
    # wandb-logged-artifact://afdsjaksdjflkasjdf12341234hv12h3v4k12j3hv41kh4v1423k14v1k2j3hv1k2j3h4v1k23h4v:[version|latest]/path
    #  scheme                                 name                                                              version      path
    path: typing.Optional[str] = None

    # private attrs
    _weave_wb_artifact_uri: typing.Optional[WeaveWBArtifactURI] = None

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
        path = path.strip("/")
        spl_netloc = netloc.split(":")
        if len(spl_netloc) == 1:
            name = spl_netloc[0]
            version = None
        elif len(spl_netloc) == 2:
            name, version = spl_netloc
        else:
            raise errors.WeaveInvalidURIError(f"Invalid WB Client Artifact URI: {uri}")

        return WeaveWBLoggedArtifactURI(name=name, version=version, path=path)

    def __str__(self) -> str:
        netloc = self.name
        if self.version:
            netloc += f":{self.version}"
        path = self.path or ""
        if path != "":
            path = f"/{path}"
        return f"{self.SCHEME}://{netloc}{path}"

    @property
    def wb_artifact_uri(self) -> WeaveWBArtifactURI:
        if self._weave_wb_artifact_uri is None:
            art_id = self.name
            if self.version:
                art_id += f":{self.version}"
            self._weave_wb_artifact_uri, _ = get_wandb_read_client_artifact_uri(art_id)
        return self._weave_wb_artifact_uri.with_path(self.path or "")

    @property
    def entity_name(self) -> str:
        return self.wb_artifact_uri.entity_name

    @property
    def project_name(self) -> str:
        return self.wb_artifact_uri.project_name

    def with_path(self, path: str) -> "WeaveWBLoggedArtifactURI":
        return WeaveWBLoggedArtifactURI(
            self.name,
            self.version,
            path,
        )

    @classmethod
    def parse(cls, uri: str) -> "WeaveWBLoggedArtifactURI":
        scheme, netloc, path, params, query_s, fragment = parse.urlparse(uri)
        return cls.from_parsed_uri(
            uri, scheme, netloc, path, params, parse.parse_qs(query_s), fragment
        )

    def to_ref(self) -> WandbArtifactRef:
        return WandbArtifactRef.from_uri(self)
