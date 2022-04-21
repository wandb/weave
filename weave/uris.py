from typing import ClassVar, Optional, Type
from urllib.parse import urlparse
from enum import Enum


class WeaveObjectLocation:
    # classvar to identify the ObjectLocation type
    scheme: ClassVar[str]

    # the path of the location (basically the full URI minus the scheme)
    path: str

    # the human-readable name of the object (Do not use this for indexing)
    _friendly_name: Optional[str] = None

    # the version (hash) of the object.
    # `None` does NOT indicate "latest" - `None` indicates that we don't know the version yet
    _version: Optional[str] = None

    # Extra parts of the path (after the version)
    extra: Optional[list[str]] = None

    def __init__(self, uri: str) -> None:
        parsed = urlparse(uri)
        if parsed.scheme != self.scheme:
            raise Exception("invalid scheme ", uri)
        self.path = parsed.netloc.strip("/") + "/" + parsed.path.strip("/")

    # URI of the object. Roughly:
    #  [scheme://][domain]/[friendly_name]/[version]/[extra]
    # This can (and should) be used to both index/cache objects
    # as well as fetch objects from remote locations.
    @property
    def uri(self) -> str:
        scheme_str = f"{self.scheme}://" if self.scheme != "" else ""
        return scheme_str + self.path

    @property
    def friendly_name(self) -> str:
        if self._friendly_name is None:
            raise Exception("no friendly name")
        return self._friendly_name

    @property
    def version(self) -> Optional[str]:
        return self._version

    # Used to parse an object URI into it's appropriate WeaveObjectLocation subclass
    @classmethod
    def parse(cls: Type["WeaveObjectLocation"], uri: str) -> "WeaveObjectLocation":
        scheme = urlparse(uri).scheme
        for candidate_class in cls.__subclasses__():
            if candidate_class.scheme == scheme:
                return candidate_class(uri)
        raise Exception("invalid scheme ", uri)


# <<<<<<< HEAD
# =======
#         parts = url.path.strip("/").split("/")
#         if len(parts) == 1:
#             path = url.netloc
#             name = parts[0]
#         else:
#             path = "/".join(parts[:-1])
#             if url.netloc:
#                 path = "/".join([url.netloc, path])
#             name = parts[len(parts) - 1]
# >>>>>>> weavehouse/process-server

# Used when the Weave object is constructed at runtime (eg. weave-builtins or user-defined objects)
class WeaveRuntimeObjectLocation(WeaveObjectLocation):
    scheme = ""

    def __init__(self, uri: str):
        super().__init__(uri)
        parts = self.path.split(":", 1)
        self._friendly_name = parts[0]
        if len(parts) == 2:
            self._version = parts[1]
        else:
            self._version = None


# Used when the Weave object is located on disk (eg after saving locally).
#
# Note: this can change over time as it is only used in-process
# local-artifact://user/timothysweeney/workspace/.../local-artifacts/<friendly_name>/<version>?extra=<extra_parts>
class WeaveLocalArtifactObjectLocation(WeaveObjectLocation):
    scheme = "local-artifact"

    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        parts = self.path.split("/")
        if len(parts) < 2:
            raise Exception("invalid uri ", uri)
        self._friendly_name = parts[-2]
        self._version = parts[-1]
        query = urlparse(uri).query
        if query is not None and "extra=" in query:
            self.extra = query.split("extra=", 1)[1].split("/")

    @classmethod
    def from_parts(
        cls: Type["WeaveLocalArtifactObjectLocation"],
        root: str,
        friendly_name: str,
        version: Optional[str] = None,
        extra: Optional[list[str]] = None,
    ) -> "WeaveLocalArtifactObjectLocation":
        return cls(cls.make_uri(root, friendly_name, version, extra))

    @staticmethod
    def make_uri(
        root: str,
        friendly_name: str,
        version: Optional[str] = None,
        extra: Optional[list[str]] = None,
    ) -> str:
        uri = (
            WeaveLocalArtifactObjectLocation.scheme + "://" + root + "/" + friendly_name
        )
        if version is not None:
            uri += "/" + version
        if extra is not None:
            uri += "?extra=" + "/".join(extra)
        return uri


# Used to refer to objects stored in WB Artifacts. This URI must not change and
# matches the existing artifact schemes
class WeaveArtifactObjectLocation(WeaveObjectLocation):
    scheme = "wandb-artifact"
    _entity_name: str
    _project_name: str
    _artifact_name: str

    def __init__(self, uri: str) -> None:
        super().__init__(uri)
        all_parts = self.path.split(":")
        if len(all_parts) != 2:
            raise Exception("invalid uri version ", uri)
        parts = all_parts[0].split("/")
        if len(parts) < 3:
            raise Exception("invalid uri parts ", uri)

        self._entity_name = parts[0]
        self._project_name = parts[1]
        self._artifact_name = parts[2]
        self._friendly_name = parts[2]
        self._version = all_parts[1]
        self.extra = parts[3:]

    @classmethod
    def from_parts(
        cls,
        entity_name: str,
        project_name: str,
        artifact_name: str,
        version: str,
        extra: Optional[list[str]] = None,
    ):
        return cls(
            cls.make_uri(entity_name, project_name, artifact_name, version, extra)
        )

    @staticmethod
    def make_uri(
        entity_name: str,
        project_name: str,
        artifact_name: str,
        version: str,
        extra: Optional[list[str]] = None,
    ):
        uri = (
            WeaveArtifactObjectLocation.scheme
            + "://"
            + entity_name
            + "/"
            + project_name
            + "/"
            + artifact_name
            + ":"
            + version
        )
        if extra is not None:
            uri += "/".join(extra)
        return uri

    def make_path(self) -> str:
        return f"{self._entity_name}/{self._project_name}/{self._artifact_name}:{self._version}"
