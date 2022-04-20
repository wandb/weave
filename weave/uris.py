from enum import Enum
from typing import Optional
from urllib.parse import urlparse
from enum import Enum


class Scheme(Enum):
    BUILTIN = 1
    LOCAL_FILE = 2
    ARTIFACT = 3


class WeaveObjectURI:
    def __init__(
        self, scheme: Scheme, path: str, name: str, version: Optional[str] = None
    ):
        self.scheme = scheme
        self.path = path.strip("/")
        self.name = name.strip("/")
        self.version = version.strip("/") if version is not None else None

    def _scheme_str(self):
        if self.scheme == Scheme.BUILTIN:
            return ""
        elif self.scheme == Scheme.LOCAL_FILE:
            return "file://"
        elif self.scheme == Scheme.ARTIFACT:
            return "wandb-artifact://"
        else:
            raise Exception("Invalid scheme")

    def uri(self):
        return f"{self._scheme_str()}{self.path}/{self.name}:{self.version if self.version is not None else 'latest'}"

    @classmethod
    def parsestr(cls, s: str):
        url = urlparse(s)
        scheme = None
        if url.scheme is None:
            scheme = Scheme.BUILTIN
        elif url.scheme == "file":
            scheme = Scheme.LOCAL_FILE
        elif url.scheme == "wandb-artifact":
            scheme = Scheme.ARTIFACT
        else:
            raise Exception("Invalid scheme")

        parts = url.path.split("/")
        if len(parts) == 1:
            path = ""
            name = parts[0]
        else:
            path = "/".join(parts[:-1])
            name = parts[len(parts) - 1]

        if ":" not in name:
            version = None
        else:
            name, version = name.split(":", 1)

        return cls(scheme, path, name, version)
