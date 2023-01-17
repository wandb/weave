import typing
from urllib import parse

from . import errors

if typing.TYPE_CHECKING:
    from . import ref_base


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

    def to_ref(self) -> "ref_base.Ref":
        raise NotImplementedError


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

    def __repr__(self) -> str:
        return f"<RuntimeURI({self.uri})>"
