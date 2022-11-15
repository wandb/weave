import typing
from urllib import parse

from . import wandb_api
from wandb.apis import public as wandb_public_api
from . import errors


class WeaveURI:
    # classvar to identify the URI type
    scheme: typing.ClassVar[str]

    # the path of the location (basically the full URI minus the scheme)
    path: str

    # the full name of this object
    _full_name: str

    # the version (hash) of the object.
    # `None` does NOT indicate "latest" - `None` indicates that we don't know the version yet
    _version: typing.Optional[str] = None

    # Extra parts of the path (after the version)
    extra: typing.Optional[list[str]] = None

    # Extra parts of the path (after the version)
    file: typing.Optional[str] = None

    def __init__(self, uri: str) -> None:
        parsed = parse.urlparse(uri)
        if parsed.scheme != self.scheme:
            raise errors.WeaveSerializeError("invalid scheme ", uri)
        self.path = parsed.netloc + parsed.path
        # default file to _obj since URI automatically strips _obj. If the user wants to access a different file
        # it will be overridden by the query param parsing below
        self.file = "_obj"

        query = parse.parse_qs(parsed.query)
        if "extra" in query:
            self.extra = query["extra"]
        if "file" in query:
            if len(query["file"]) > 1:
                raise errors.WeaveSerializeError(
                    f"URIs do not support multiple file parameters - {query['file']}"
                )
            self.file = query["file"][0]

    @staticmethod
    def _generate_query_str(
        extra: typing.Optional[list[str]] = None, file: typing.Optional[str] = None
    ):
        query_dict = {}
        if extra is not None and len(extra) > 0:
            query_dict["extra"] = extra
        # should we continue special casing _obj like this?
        if file and file != "_obj":
            query_dict["file"] = [file]

        query_str = ""
        if len(query_dict) > 0:
            query_str = "?" + parse.urlencode(query_dict, True)

        return query_str

    # URI of the object. Roughly:
    #  [scheme://][domain]/[friendly_name]/[version]?extra=[extra]&path=[path]
    # This can (and should) be used to both index/cache objects
    # as well as fetch objects from remote locations.
    @property
    def uri(self) -> str:
        scheme_str = f"{self.scheme}://" if self.scheme != "" else ""

        return (
            scheme_str + self.path + WeaveURI._generate_query_str(self.extra, self.file)
        )

    @property
    def friendly_name(self) -> str:
        # strip off the prefix before the first "-" since the convention for builin ops are <type>-<op-name>
        parts = self._full_name.rsplit("-", 1)
        if len(parts) > 1:
            return parts[1]
        return parts[0]

    @property
    def full_name(self) -> str:
        return self._full_name

    @property
    def version(self) -> typing.Optional[str]:
        return self._version

    # Used to parse an object URI into it's appropriate WeaveURI subclass
    @classmethod
    def parse(cls: typing.Type["WeaveURI"], uri: str) -> "WeaveURI":
        scheme = parse.urlparse(uri).scheme
        for candidate_class in cls.__subclasses__():
            if candidate_class.scheme == scheme:
                return candidate_class(uri)
        raise errors.WeaveInternalError("invalid scheme ", uri)


# Used when the Weave object is constructed at runtime (eg. weave-builtins or user-defined objects)
class WeaveRuntimeURI(WeaveURI):
    scheme = ""

    def __init__(self, uri: str):
        super().__init__(uri)
        parts = self.path.split(":", 1)
        self._full_name = parts[0]
        if len(parts) == 2:
            self._version = parts[1]
        else:
            self._version = None


# Used when the Weave object is located on disk (eg after saving locally).
#
# Note: this can change over time as it is only used in-process
# local-artifact://user/timothysweeney/workspace/.../local-artifacts/<friendly_name>/<version>?extra=<extra_parts>
class WeaveLocalArtifactURI(WeaveURI):
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

        uri = uri + WeaveURI._generate_query_str(extra, file)
        return uri


# Used to refer to objects stored in WB Artifacts. This URI must not change and
# matches the existing artifact schemes
class WeaveWBArtifactURI(WeaveURI):
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

        uri = uri + WeaveURI._generate_query_str(extra, file)
        return uri

    def make_path(self) -> str:
        return f"{self._entity_name}/{self._project_name}/{self._artifact_name}:{self._version}"


class WeaveWBClientArtifactURI(WeaveURI):
    scheme = "wandb-client-artifact"
    _client_id: str

    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        all_parts = self.path.split(":")
        if len(all_parts) != 2:
            raise errors.WeaveInternalError("invalid uri version ", uri)
        self._client_id = all_parts[0].strip("/")
        self._version = all_parts[1].split("/", 1)[0]
        self._file = all_parts[1].split("/", 1)[1]
        self._full_name = self._client_id

    def make_path(self) -> str:
        query = wandb_public_api.gql(
            """
        query ArtifactVersion(
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
                "id": self._client_id,
                "aliasName": self._version,
            },
        )
        entity_name = res["artifactCollection"]["project"]["entity"]["name"]
        project_name = res["artifactCollection"]["project"]["name"]
        # artifact_type_name = res["artifactCollection"]["defaultArtifactType"][
        #     "name"
        # ]
        artifact_name = res["artifactCollection"]["name"]
        version_index = res["artifactCollection"]["artifactMembership"]["versionIndex"]
        version = f"v{version_index}"
        return f"{entity_name}/{project_name}/{artifact_name}:{version}"
        # return f"{self._client_id}:{self._version}/{self._file}"
