import contextlib
import json
import os
import random
import shutil
import pathlib
import tempfile
import typing

import wandb
from wandb.apis import public as wb_public
from wandb.util import hex_to_b64_id

from . import uris
from . import errors
from . import wandb_api
from . import memo

from . import weave_types as types
from . import artifact_fs
from . import artifact_util

if typing.TYPE_CHECKING:
    from .ops_domain.file_wbartifact import ArtifactVersionFile


@memo.memo
def get_wandb_read_artifact(path):
    return wandb_api.wandb_public_api().artifact(path)


@memo.memo
def get_wandb_read_run(path):
    return wandb_api.wandb_public_api().run(path)


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

    weave_art_uri = WeaveWBArtifactURI.from_parts(
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


class WandbArtifact(artifact_fs.FilesystemArtifact):
    def __init__(
        self, name, type=None, uri: typing.Optional["WeaveWBArtifactURI"] = None
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
        uri = WeaveWBArtifactURI.from_parts(run.entity, project, a_name, a_version)
        self._set_read_artifact_uri(uri)


class WandbRunFilesProxyArtifact(artifact_fs.FilesystemArtifact):
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


# This should not be declared here, but WandbArtifactRef.type needs to
# be able to create it right now, because of a series of hacks.
# Instead, We probably need a WandbArtifactFileRef.
# TODO: fix
class ArtifactVersionFileType(types.Type):
    _base_type = types.FileType()

    name = "ArtifactVersionFile"

    extension = types.String()
    wb_object_type = types.String()

    def save_instance(
        self,
        obj: "ArtifactVersionFile",
        artifact: artifact_fs.FilesystemArtifact,
        name: str,
    ) -> "WandbArtifactRef":
        return WandbArtifactRef(obj.artifact, obj.path)

    # load_instance is injected by file_wbartifact.py in ops_domain.
    # Bad bad bad!
    # TODO: fix


class WandbArtifactRef(artifact_fs.FilesystemArtifactRef):
    FileType = ArtifactVersionFileType

    artifact: WandbArtifact

    def versions(self) -> list[artifact_fs.FilesystemArtifactRef]:
        # TODO: implement versions on wandb artifact
        return [self]

    @classmethod
    def from_uri(cls, uri: uris.WeaveURI) -> "WandbArtifactRef":
        if not isinstance(uri, WeaveWBArtifactURI):
            raise errors.WeaveInternalError(
                f"Invalid URI class passed to WandbArtifactRef.from_uri: {type(uri)}"
            )
        # TODO: potentially need to pass full entity/project/name instead
        return cls(
            WandbArtifact(uri.full_name, uri=uri),
            path=uri.file,
        )


types.WandbArtifactRefType.instance_class = WandbArtifactRef
types.WandbArtifactRefType.instance_classes = WandbArtifactRef

WandbArtifact.RefClass = WandbArtifactRef

# Used to refer to objects stored in WB Artifacts. This URI must not change and
# matches the existing artifact schemes
class WeaveWBArtifactURI(uris.WeaveURI):
    scheme = "wandb-artifact"
    _entity_name: str
    _project_name: str
    _artifact_name: str

    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        all_parts = self.path.split(":")
        if len(all_parts) != 2:
            raise errors.WeaveInternalError("invalid uri version ", uri)
        parts = all_parts[0].split("/")
        if len(parts) < 3:
            raise errors.WeaveInternalError("invalid uri parts ", uri)

        self._entity_name = parts[0].strip("/")
        self._project_name = parts[1].strip("/")
        self._artifact_name = parts[2].strip("/")
        self._full_name = parts[2].strip("/")
        self._version = all_parts[1]

    @classmethod
    def from_parts(
        cls,
        entity_name: str,
        project_name: str,
        artifact_name: str,
        version: str,
        extra: typing.Optional[list[str]] = None,
        file: typing.Optional[str] = None,
    ):
        return cls(
            cls.make_uri(entity_name, project_name, artifact_name, version, extra, file)
        )

    @staticmethod
    def make_uri(
        entity_name: str,
        project_name: str,
        artifact_name: str,
        version: str,
        extra: typing.Optional[list[str]] = None,
        file: typing.Optional[str] = None,
    ):
        uri = (
            WeaveWBArtifactURI.scheme
            + "://"
            + entity_name
            + "/"
            + project_name
            + "/"
            + artifact_name
            + ":"
            + version
        )

        uri = uri + uris.WeaveURI._generate_query_str(extra, file)
        return uri

    def make_path(self) -> str:
        return f"{self._entity_name}/{self._project_name}/{self._artifact_name}:{self._version}"

    def to_ref(self) -> WandbArtifactRef:
        return WandbArtifactRef.from_uri(self)
