import re
import contextlib
import dataclasses
import os
import functools
import tempfile
import typing
import requests
import logging

from wandb import Artifact
from wandb.apis import public as wb_public
from wandb.sdk.lib.hashutil import hex_to_b64_id, b64_to_hex_id


from . import uris
from . import util
from . import errors
from . import wandb_client_api
from . import file_base
from . import file_util

from . import weave_types as types
from . import artifact_fs
from . import filesystem
from . import memo
from .wandb_interface import wandb_artifact_pusher
from . import engine_trace

from urllib import parse

if typing.TYPE_CHECKING:
    from weave.wandb_interface.wandb_lite_run import InMemoryLazyLiteRun


quote_slashes = functools.partial(parse.quote, safe="")

DEFAULT_WEAVE_OBJ_PROJECT = "weave"


class WandbArtifactManifestEntry(typing.TypedDict):
    digest: str
    birthArtifactID: typing.Optional[str]
    ref: typing.Optional[str]
    size: typing.Optional[int]
    extra: typing.Optional[dict[str, typing.Any]]
    # wandb.sdk.wandb_artifacts.ArtifactManifestEntry also has "local_path"
    # but that doesn't exist in saved manifests


class WandbArtifactManifestV1(typing.TypedDict):
    version: int
    storagePolicy: str
    storagePolicyConfig: typing.Optional[dict[str, typing.Any]]
    contents: typing.Dict[str, WandbArtifactManifestEntry]


# We used to use wandb.sdk.wandb_artifacts.ArtifactManifest directly, but it
# is expensive to construct because it makes new objects for every entry and
# causes a lot of memory/gc churn. This implementation leaves the manifest
# as the raw json dict instead.
@dataclasses.dataclass
class WandbArtifactManifest:
    class StorageLayout:
        V1 = "V1"
        V2 = "V2"

    _manifest_json: WandbArtifactManifestV1

    @property
    def _storage_policy_config(self):
        return self._manifest_json.get("storagePolicyConfig", {})

    @property
    def storage_layout(self):
        return self._storage_policy_config.get(
            "storageLayout", WandbArtifactManifest.StorageLayout.V1
        )

    def get_entry_by_path(
        self, path: str
    ) -> typing.Optional[WandbArtifactManifestEntry]:
        return self._manifest_json["contents"].get(path)

    def get_paths_in_directory(self, path: str) -> typing.List[str]:
        if path == "":
            return list(self._manifest_json["contents"].keys())
        dir_path = path + "/"
        return [
            k for k in self._manifest_json["contents"].keys() if k.startswith(dir_path)
        ]


# TODO: Get rid of this, we have the new wandb api service! But this
# is still used in a couple places.
@memo.memo  # Per-request memo reduces duplicate calls to the API
def get_wandb_read_artifact(path: str):
    tracer = engine_trace.tracer()
    with tracer.trace("get_wandb_read_artifact"):
        return wandb_client_api.wandb_public_api().artifact(path)


def is_valid_version_index(version_index: str) -> bool:
    return bool(re.match(r"^v(0|[1-9][0-9]*)$", version_index))


def get_wandb_read_artifact_uri(path: str):
    tracer = engine_trace.tracer()
    with tracer.trace("get_wandb_read_artifact_uri"):
        art = get_wandb_read_artifact(path)
        return WeaveWBArtifactURI(
            art.name.split(":", 1)[0],
            art.commit_hash,
            art.entity,
            art.project,
        )


def wandb_artifact_dir():
    d = os.path.join(filesystem.get_filesystem_dir(), "wandb_artifacts")
    os.makedirs(d, exist_ok=True)
    return d


@dataclasses.dataclass
class ReadClientArtifactURIResult:
    weave_art_uri: "WeaveWBArtifactURI"
    artifact_type_name: str
    is_deleted: bool


def _art_id_is_client_version_id_mapping(art_id: str) -> bool:
    return len(art_id) == 128 and ":" not in art_id


def _art_id_is_client_collection_and_alias_id_mapping(art_id: str) -> bool:
    return ":" in art_id


def _convert_client_id_to_server_id(art_id: str) -> str:
    query = wb_public.gql(
        """
        query ClientIDMapping($clientID: ID!) {
            clientIDMapping(clientID: $clientID) {
                serverID
            }
        }
    """
    )
    tracer = engine_trace.tracer()
    with tracer.trace("_convert_client_id_to_server_id.execute"):
        res = wandb_client_api.wandb_public_api().client.execute(
            query,
            variable_values={
                "clientID": art_id,
            },
        )
    return b64_to_hex_id(res["clientIDMapping"]["serverID"])


def _collection_and_alias_id_mapping_to_uri(
    client_collection_id: str, alias_name: str
) -> ReadClientArtifactURIResult:
    is_deleted = False
    query = """
    query ArtifactVersionFromIdAlias(
        $id: ID!,
        $aliasName: String!
    ) {
        artifactCollection(id: $id) {
            id
            name
            state
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
                commitHash
            }
            artifactMemberships(first: 1) {
                edges {
                    node {
                        id
                        versionIndex
                        commitHash
                    }
                }
            }
            defaultArtifactType {
                id
                name
            }
        }
    }
    """

    try:
        tracer = engine_trace.tracer()
        with tracer.trace("_collection_and_alias_id_mapping_to_uri.execute"):
            res = wandb_client_api.query_with_retry(
                query,
                variables={
                    "id": client_collection_id,
                    "aliasName": alias_name,
                },
                num_timeout_retries=1,
            )
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            # This is a special case: the client id corresponds to an artifact that was
            # never uploaded, so the client id doesn't exist in the W&B server.

            collection = None
            logging.warn(
                f"Artifact collection with client id {client_collection_id} not present in W&B server."
            )

        else:
            raise e
    else:
        collection = res["artifactCollection"]

    if collection is None:
        # Note: deleted collections are still returned by the API (with state=DELETED)
        # So a missing collection is a real error (unless it was never uploaded)
        raise errors.WeaveArtifactCollectionNotFound(
            f"Could not find artifact collection with client id {client_collection_id}"
        )
    elif collection["state"] != "READY":  # state is either "DELETED" or "READY"
        # This is a deleted artifact, but we still have a record of it.
        is_deleted = True

    artifact_type_name = res["artifactCollection"]["defaultArtifactType"]["name"]
    artifact_membership = res["artifactCollection"]["artifactMembership"]
    if artifact_membership is None:
        # Here we account for a special case: when the alias is `latest`. It is
        # exceedingly common and expected to reference the latest alias of a
        # collection. This is particularly common when logging tables (but used
        # in many other places as well). Occasionally the user deletes the
        # `latest` alias which is a super easy thing to do in the UI. However,
        # this results in the data not being found. We solved this similarly in
        # the typescript implementation by getting the most recent version in
        # such cases. At one point we had an extended discussion about making
        # `latest` a "calculated" alias, which would solve this issue on
        # gorilla's side, but were unable to reach an actionable conclusion.
        # This is a simple workaround that solves for these cases.
        if (
            alias_name == "latest"
            and len(res["artifactCollection"]["artifactMemberships"]["edges"]) > 0
        ):
            commit_hash = res["artifactCollection"]["artifactMemberships"]["edges"][0][
                "node"
            ]["commitHash"]
        else:
            is_deleted = True
            # If the membership is deleted, then we will not be able to get the commit hash.
            # Here, we can simply use the alias name as the commit hash. If the collection
            # is ever un-deleted or the alias is re-assigned, then the next call will result
            # in a "true" commit hash, ensuring we don't hit a stale cache.
            commit_hash = alias_name
    else:
        commit_hash = artifact_membership["commitHash"]
    entity_name = collection["project"]["entity"]["name"]
    project_name = collection["project"]["name"]
    artifact_name = collection["name"]

    weave_art_uri = WeaveWBArtifactURI(
        artifact_name,
        commit_hash,
        entity_name,
        project_name,
    )

    return ReadClientArtifactURIResult(weave_art_uri, artifact_type_name, is_deleted)


def _version_server_id_to_uri(server_id: str) -> ReadClientArtifactURIResult:
    is_deleted = False
    query = wb_public.gql(
        """
    query ArtifactVersionFromServerId(
        $id: ID!,
    ) {
        artifact(id: $id) {
            id
            state
            commitHash
            versionIndex
            artifactType {
                id
                name
            }
            artifactSequence {
                id
                name
                state
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
    tracer = engine_trace.tracer()
    with tracer.trace("_version_server_id_to_uri.execute"):
        res = wandb_client_api.wandb_public_api().client.execute(
            query,
            variable_values={"id": hex_to_b64_id(server_id)},
        )

    artifact = res["artifact"]
    if artifact is None:
        # Note: deleted versions are still returned by the API (with state=DELETED)
        # So a missing artifact is a real error.
        raise errors.WeaveArtifactVersionNotFound(
            f"Could not find artifact version with server id {server_id}"
        )
    elif (
        artifact["state"] != "COMMITTED"
    ):  # state is either "DELETED" or "PENDING" or "COMMITTED"
        # This is a deleted artifact, but we still have a record of it
        is_deleted = True

    collection = artifact["artifactSequence"]

    if collection is None:
        # Note: deleted collections are still returned by the API (with state=DELETED)
        # So a missing collection is a real error.
        raise errors.WeaveArtifactCollectionNotFound(
            f"Could not find artifact sequence for artifact version with server id {server_id}"
        )
    elif collection["state"] != "READY":  # state is either "DELETED" or "READY"
        # This is a deleted artifact, but we still have a record of it
        is_deleted = True

    artifact_type_name = artifact["artifactType"]["name"]
    commit_hash = artifact["commitHash"]

    entity_name = collection["project"]["entity"]["name"]
    project_name = collection["project"]["name"]
    artifact_name = collection["name"]

    weave_art_uri = WeaveWBArtifactURI(
        artifact_name,
        commit_hash,
        entity_name,
        project_name,
    )

    return ReadClientArtifactURIResult(weave_art_uri, artifact_type_name, is_deleted)


def get_wandb_read_client_artifact_uri(art_id: str) -> ReadClientArtifactURIResult:
    """art_id may be client_id, seq:alias, or server_id"""
    tracer = engine_trace.tracer()
    with tracer.trace("get_wandb_read_client_artifact_uri"):
        if _art_id_is_client_version_id_mapping(art_id):
            server_id = _convert_client_id_to_server_id(art_id)
            return _version_server_id_to_uri(server_id)
        elif _art_id_is_client_collection_and_alias_id_mapping(art_id):
            client_collection_id, alias_name = art_id.split(":")
            return _collection_and_alias_id_mapping_to_uri(
                client_collection_id, alias_name
            )
        else:
            return _version_server_id_to_uri(art_id)


def get_wandb_read_client_artifact(art_id: str) -> typing.Optional["WandbArtifact"]:
    """art_id may be client_id, seq:alias, or server_id"""
    tracer = engine_trace.tracer()
    with tracer.trace("get_wandb_read_client_artifact"):
        res = get_wandb_read_client_artifact_uri(art_id)
        if res.is_deleted:
            return None
        return WandbArtifact(
            res.weave_art_uri.name, res.artifact_type_name, res.weave_art_uri
        )


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

        self.io_service = io_service.get_sync_client()
        self.name = name

        # original uri passed, if any. this can include aliases such as latest or best, which do not
        # correspond to specific versions or may change versions.
        self._unresolved_read_artifact_or_client_uri = None

        # resolved version of the URI above. this points to the same artifact as the unresolved URI but
        # includes a specific, immutable version like v4 instead of an alias. this is needed for idempotency
        # of cache keys.
        self._resolved_read_artifact_uri: typing.Optional["WeaveWBArtifactURI"] = None
        self._read_artifact = None
        if not uri:
            self._writeable_artifact = Artifact(
                name, "op_def" if type is None else type
            )
        else:
            # load an existing artifact, this should be read only,
            # TODO: we could technically support writable artifacts by creating a new version?
            self._unresolved_read_artifact_or_client_uri = uri
        self._local_path: dict[str, str] = {}

    @property
    def branch(self) -> typing.Optional[str]:
        if self._unresolved_read_artifact_or_client_uri is not None:
            branch = self._unresolved_read_artifact_or_client_uri.version

        if branch is not None and not likely_commit_hash(branch):
            return branch

        return None

    @property
    def branch_point(self) -> typing.Optional[artifact_fs.BranchPointType]:
        # all branching is local for now. we could support remote branches
        # but in this initial implementation, assume only LocalArtifacts
        # live on branches.
        return None

    @property
    def _read_artifact_uri(self) -> typing.Optional["WeaveWBArtifactURI"]:
        if self._resolved_read_artifact_uri is not None:
            return self._resolved_read_artifact_uri

        if isinstance(
            self._unresolved_read_artifact_or_client_uri,
            (WeaveWBLoggedArtifactURI, WeaveWBArtifactURI),
        ):
            self._resolved_read_artifact_uri = (
                self._unresolved_read_artifact_or_client_uri.resolved_artifact_uri
            )
        return self._resolved_read_artifact_uri

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
        self._resolved_read_artifact_uri = None
        self._unresolved_read_artifact_or_client_uri = uri

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

    def delete(self) -> None:
        self._saved_artifact.delete(delete_aliases=True)

    def add_artifact_reference(self, uri: str) -> None:
        # The URI for a get node might look like: wandb-artifact:///<entity>/<project>/test8:latest/obj
        # but the SDK add_reference call requires something like:
        # wandb-artifact://41727469666163743a353432353830303535/obj.object.json
        assert uri.startswith("wandb-artifact:///")
        uri_parts = WeaveWBArtifactURI.parse(uri)
        uri_path = f"{uri_parts.entity_name}/{uri_parts.project_name}/{uri_parts.name}:{uri_parts.version}"
        ref_artifact = get_wandb_read_artifact(uri_path)

        # A reference needs to point to a specific existing file in the other artifact.
        # For stream tables obj.object.json should exist. For logged tables, the filename
        # can vary, so we just pick the first file we find.
        filename = "obj.object.json"
        try:
            ref_url = ref_artifact.get_path(filename).ref_url()
        except KeyError:
            for ref_file in ref_artifact.files(None, per_page=1):
                ref_url = ref_artifact.get_path(ref_file.name).ref_url()
                break

        # We have a name collision problem. E.g. A board and a stream table will both have
        # a file named obj.object.json. Add a prefix to distinguish them.
        ref_name = f"{ref_artifact.id}__{filename}"
        self._writeable_artifact.add_reference(ref_url, ref_name)

    @property
    def commit_hash(self) -> str:
        if not self.is_saved:
            raise errors.WeaveInternalError(
                "cannot get commit hash of an unsaved artifact"
            )
        resolved_uri = self._read_artifact_uri
        if resolved_uri is None:
            raise errors.WeaveInternalError("cannot resolve commit hash of artifact")
        version = resolved_uri.version
        if version is None:
            raise errors.WeaveInternalError("resolved uri has no version")
        return version

    @property
    def is_saved(self) -> bool:
        return (
            self._unresolved_read_artifact_or_client_uri is not None
            or self._read_artifact is not None
        )

    @property
    def version(self):
        if not self.is_saved:
            raise errors.WeaveInternalError("cannot get version of an unsaved artifact")

        # Note: W&B Artifact's `version` is often the `v0` alias, which is not what
        # we want here (despite the same name for the property). In Weave world, `version`
        # refers to either: a) a commit hash, or b) a branch name. Therefore, in this
        # case, we explicitly want the commit hash, not the differently-defined `version`.
        return self._saved_artifact.commit_hash

    @property
    def created_at(self):
        raise NotImplementedError()

    def get_other_version(self, version):
        raise NotImplementedError()

    def direct_url(self, path: str) -> typing.Optional[str]:
        if self._read_artifact_uri is None:
            raise errors.WeaveInternalError(
                'cannot get direct url for unsaved artifact"'
            )
        uri = self._read_artifact_uri.with_path(path)
        return self.io_service.direct_url(uri)

    def path(self, name: str) -> str:
        if not self.is_saved or not self._read_artifact_uri:
            raise errors.WeaveInternalError("cannot download of an unsaved artifact")

        uri = self._read_artifact_uri.with_path(name)
        fs_path = self.io_service.ensure_file(uri)
        if fs_path is None:
            # Important to raise FileNotFoundError here, FileSystemArtifactRef.type
            # relies on this.
            raise FileNotFoundError("Path not in artifact")
        return self.io_service.fs.path(fs_path)

    def size(self, path: str) -> int:
        manifest = self._manifest()
        if manifest is not None:
            manifest_entry = manifest.get_entry_by_path(path)
            if manifest_entry:
                size = manifest_entry["size"]
                if size is None:
                    return 0
                return size

        if path in self._saved_artifact.manifest.entries:
            return self._saved_artifact.manifest.entries[path].size
        return super().size(path)

    @property
    def initial_uri_obj(
        self,
    ) -> typing.Union["WeaveWBArtifactURI", "WeaveWBLoggedArtifactURI"]:
        if not self.is_saved or not self._unresolved_read_artifact_or_client_uri:
            raise errors.WeaveInternalError("cannot get uri of an unsaved artifact")
        return self._unresolved_read_artifact_or_client_uri

    @property
    def uri_obj(self) -> "WeaveWBArtifactURI":
        if not self.is_saved or not self._read_artifact_uri:
            raise errors.WeaveInternalError("cannot get uri of an unsaved artifact")
        return self._read_artifact_uri

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

    def save(
        self,
        project: str = DEFAULT_WEAVE_OBJ_PROJECT,
        entity_name: typing.Optional[str] = None,
        branch: typing.Optional[str] = None,
        *,
        _lite_run: typing.Optional["InMemoryLazyLiteRun"] = None,
    ):
        additional_aliases = [] if branch is None else [branch]
        res = wandb_artifact_pusher.write_artifact_to_wandb(
            self._writeable_artifact,
            project,
            entity_name,
            additional_aliases,
            _lite_run=_lite_run,
        )
        version = res.version_str if branch is None else branch
        self._set_read_artifact_uri(
            WeaveWBArtifactURI(
                name=res.artifact_name,
                version=version,
                entity_name=res.entity_name,
                project_name=res.project_name,
            )
        )

    def _manifest(self) -> typing.Optional[WandbArtifactManifest]:
        if self._read_artifact_uri is None:
            raise errors.WeaveInternalError(
                'cannot get path info for unsaved artifact"'
            )
        return self.io_service.manifest(self._read_artifact_uri)

    def digest(self, path: str) -> typing.Optional[str]:
        manifest_entry = self._manifest_entry(path)
        if manifest_entry is not None:
            return manifest_entry["digest"]
        return None

    def _manifest_entry(self, path: str) -> typing.Optional[WandbArtifactManifestEntry]:
        manifest = self._manifest()
        if manifest is not None:
            manifest_entry = manifest.get_entry_by_path(path)
            if manifest_entry is not None:
                return manifest_entry
        return None

    def _path_info(
        self, path: str
    ) -> typing.Optional[
        typing.Union[
            "artifact_fs.FilesystemArtifactFile",
            "artifact_fs.FilesystemArtifactDir",
            "artifact_fs.FilesystemArtifactRef",
        ]
    ]:
        manifest = self._manifest()
        if manifest is None:
            return None
        manifest_entry = manifest.get_entry_by_path(path)
        if manifest_entry is not None:
            # This is not a WeaveURI! Its the artifact reference style used
            # by the W&B Artifacts/media layer.
            ref_prefix = "wandb-artifact://"
            ref = manifest_entry.get("ref")
            if ref and ref.startswith(ref_prefix):
                # This is a reference to another artifact
                art_id, target_path = ref[len(ref_prefix) :].split("/", 1)
                art = get_wandb_read_client_artifact(art_id)
                # this should be None when the requested artifact is deleted from the server.
                # we want to return None in this case so that the caller can handle it.
                if art is None:
                    return None
                return artifact_fs.FilesystemArtifactFile(art, target_path)
            # This is a file
            return artifact_fs.FilesystemArtifactFile(self, path)

        # This is not a file, assume its a directory. If not, we'll return an empty result.
        dir_paths = manifest.get_paths_in_directory(path)
        sub_dirs: dict[str, file_base.SubDir] = {}
        files = {}
        total_size = 0
        sub_dir_sizes = {}
        cwd = os.getcwd()
        for entry_path in dir_paths:
            entry = manifest.get_entry_by_path(entry_path)
            path_size = (
                entry["size"] if entry is not None and entry["size"] is not None else 0
            )
            total_size += path_size

            # this used to be os.path.relpath but that called os.getcwd() every time
            # that turned out to be a bottleneck in production for artifacts with many
            # dir paths, so we use our own implementation that takes the cwd as input
            # and doesn't need to ever call os.getcwd()
            rel_path = util.relpath_no_syscalls(entry_path, path, cwd)
            rel_path_parts = rel_path.split("/")
            if len(rel_path_parts) == 1:
                files[rel_path_parts[0]] = artifact_fs.FilesystemArtifactFile(
                    self,
                    entry_path,
                )
            else:
                dir_name = rel_path_parts[0]
                if dir_name not in sub_dirs:
                    dir_ = file_base.SubDir(entry_path, 0, {}, {})
                    sub_dir_sizes[dir_name] = 0
                    sub_dirs[dir_name] = dir_
                sub_dir_sizes[dir_name] += path_size
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
        for dir_name, dir_ in sub_dirs.items():
            dir_.size = sub_dir_sizes[dir_name]
        return artifact_fs.FilesystemArtifactDir(
            self, path, total_size, sub_dirs, files
        )

    def _get_file_paths(self) -> list[str]:
        manifest = self._manifest()
        if manifest is None:
            raise errors.WeaveInternalError("No manifest when fetching file paths")
        return manifest.get_paths_in_directory("")

    @property
    def metadata(self) -> artifact_fs.ArtifactMetadata:
        mutable_metadata = {}
        readonly_metadata = {}
        if (
            hasattr(self, "_writeable_artifact")
            and self._writeable_artifact is not None
        ):
            mutable_metadata = self._writeable_artifact.metadata
        if self.is_saved:
            readonly_metadata = self._saved_artifact.metadata
        return artifact_fs.ArtifactMetadata(mutable_metadata, readonly_metadata)


WandbArtifactType.instance_classes = WandbArtifact


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


def is_hex_string(s: str) -> bool:
    try:
        int(s, 16)
        return True
    except ValueError:
        return False


WANDB_COMMIT_HASH_LENGTH = 20


def likely_commit_hash(version: str) -> bool:
    # This is the heuristic we use everywhere to tell if a version is an alias or not
    # if self.version:
    return is_hex_string(version) and len(version) == WANDB_COMMIT_HASH_LENGTH


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

    # resolved version of the artifact uri, in which aliases are replaced with specific versions
    _resolved_artifact_uri: typing.Optional["WeaveWBArtifactURI"] = None

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
        parts = [parse.unquote(part) for part in parts]
        if len(parts) < 3:
            raise errors.WeaveInvalidURIError(f"Invalid WB Artifact URI: {uri}")
        entity_name = parts[0]
        project_name = parts[1]

        if ":" in parts[2]:
            name, version = parts[2].split(":", 1)
        else:
            name = parts[2]
            version = None

        file_path: typing.Optional[str] = None
        if len(parts) > 3:
            file_path = "/".join(parts[3:])

        extra: typing.Optional[list[str]] = None
        if fragment:
            extra = fragment.split("/")
        return cls(
            name,
            version,
            entity_name,
            project_name,
            netloc,
            file_path,
            extra,
        )

    @classmethod
    def parse(cls: typing.Type["WeaveWBArtifactURI"], uri: str) -> "WeaveWBArtifactURI":
        return super().parse(uri)  # type: ignore

    def __str__(self) -> str:
        netloc = self.netloc or ""
        uri = (
            f"{self.SCHEME}://"
            f"{quote_slashes(netloc)}/"
            f"{quote_slashes(self.entity_name)}/"
            f"{quote_slashes(self.project_name)}/"
            f"{quote_slashes(self.name)}:{self.version if self.version else ''}"
        )
        if self.path:
            uri += f"/{quote_slashes(self.path)}"
        if self.extra:
            uri += f"#{'/'.join([quote_slashes(e) for e in self.extra])}"
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

    @property
    def resolved_artifact_uri(self) -> "WeaveWBArtifactURI":
        if self.version and likely_commit_hash(self.version):
            return self
        if self._resolved_artifact_uri is None:
            path = f"{self.entity_name}/{self.project_name}/{self.name}"
            if self.version:
                path += f":{self.version}"
            resolved_artifact_uri = get_wandb_read_artifact_uri(path)
            self._resolved_artifact_uri = resolved_artifact_uri
        return self._resolved_artifact_uri

    def to_ref(self) -> WandbArtifactRef:
        return WandbArtifactRef.from_uri(self)


@dataclasses.dataclass
class WeaveWBLoggedArtifactURI(uris.WeaveURI):
    SCHEME = "wandb-logged-artifact"
    # wandb-logged-artifact://afdsjaksdjflkasjdf12341234hv12h3v4k12j3hv41kh4v1423k14v1k2j3hv1k2j3h4v1k23h4v:[version|latest]/path
    #  scheme                                 name                                                              version      path
    path: typing.Optional[str] = None

    # private attrs

    # resolved version of the artifact uri, in which aliases are replaced with specific versions
    _resolved_artifact_uri: typing.Optional[WeaveWBArtifactURI] = None

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
        path = parse.unquote(path.strip("/"))
        spl_netloc = netloc.split(":")
        if len(spl_netloc) == 1:
            name = spl_netloc[0]
            version = None
        elif len(spl_netloc) == 2:
            name, version = spl_netloc
        else:
            raise errors.WeaveInvalidURIError(f"Invalid WB Client Artifact URI: {uri}")

        return WeaveWBLoggedArtifactURI(
            name=name,
            version=version,
            path=path,
        )

    def __str__(self) -> str:
        netloc = self.name
        if self.version:
            netloc += f":{self.version}"
        path = self.path or ""
        if path != "":
            path = f"/{path}"
        return f"{self.SCHEME}://{netloc}{path}"

    @property
    def resolved_artifact_uri(self) -> WeaveWBArtifactURI:
        if self._resolved_artifact_uri is None:
            art_id = self.name
            if self.version:
                # version is the alias or version index string
                art_id += f":{self.version}"
            res = get_wandb_read_client_artifact_uri(art_id)
            self._resolved_artifact_uri = res.weave_art_uri
        return self._resolved_artifact_uri.with_path(self.path or "")

    @property
    def entity_name(self) -> str:
        return self.resolved_artifact_uri.entity_name

    @property
    def project_name(self) -> str:
        return self.resolved_artifact_uri.project_name

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


# This is a wrapper around an artifact that acts like a list of files.
# It fetchs a file from the manifest on __getItem__ and can return a count without fetching all files
@dataclasses.dataclass
class FilesystemArtifactFileIterator(list[artifact_fs.FilesystemArtifactFile]):
    data: list[str]
    artifact: WandbArtifact
    idx: int = 0

    def __init__(self, artifact: WandbArtifact, data: list[str] = []):
        self.data = data if len(data) > 0 else artifact._get_file_paths()
        self.artifact = artifact
        self.idx = 0

    def __getitem__(self, key):
        path_or_paths = self.data[key]
        if isinstance(path_or_paths, str):
            return self.artifact._path_info(path_or_paths)
        elif isinstance(path_or_paths, list):
            return FilesystemArtifactFileIterator(self.artifact, path_or_paths)
        raise errors.WeaveInternalError(
            "Invalid key in FilesystemArtifactFileIterator __getItem__"
        )

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self):
        return self

    def __next__(self):
        if self.idx >= len(self.data):
            raise StopIteration
        current_element = self.__getitem__(self.idx)
        self.idx += 1
        return current_element
