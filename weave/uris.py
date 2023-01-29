import dataclasses
import typing
from urllib import parse

from . import errors

if typing.TYPE_CHECKING:
    from . import ref_base


@dataclasses.dataclass
class WeaveURI:
    # classvar to identify the URI type
    SCHEME: typing.ClassVar[typing.Optional[str]] = None
    name: str
    version: typing.Optional[str]

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
        raise NotImplementedError

    # Used to parse an object URI into it's appropriate WeaveURI subclass
    @classmethod
    def parse(cls: typing.Type["WeaveURI"], uri: str) -> "WeaveURI":
        scheme, netloc, path, params, query_s, fragment = parse.urlparse(uri)
        query = parse.parse_qs(query_s)

        for candidate_class in [cls] + cls.__subclasses__():
            if candidate_class.SCHEME == scheme:
                return candidate_class.from_parsed_uri(
                    uri, scheme, netloc, path, params, query, fragment
                )
        raise errors.WeaveInternalError("invalid scheme ", uri)

    def __str__(self) -> str:
        raise NotImplementedError

    def to_ref(self) -> "ref_base.Ref":
        raise NotImplementedError


# Used when the Weave object is constructed at runtime (eg. weave-builtins or user-defined objects)
@dataclasses.dataclass
class WeaveRuntimeURI(WeaveURI):
    SCHEME = ""

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
        parts = path.split(":", 1)
        name = parts[0]
        version: typing.Optional[str] = None
        if len(parts) == 2:
            version = parts[1]
        return cls(name, version)

    def __str__(self):
        if self.version is not None:
            return f"{self.name}:{self.version}"
        return self.name
