# This file contains the definition for "Internal" weave refs. These should never be
# exposed to the user and should only be used internally by the weave-trace service.
# Specifically, the user-space operates on plain-text `entity/project` scopes. While
# internally, we operate on internal `project_id`s scopes. At rest, and in the database,
# we store the internal `project_id`. However, over the wire, we use the plain-text. Practically,
# the trace interface should only ever operate on internal refs.

import dataclasses
from typing import Union
from urllib.parse import quote as urllib_quote
from urllib.parse import unquote

WEAVE_INTERNAL_SCHEME = "weave-trace-internal"
WEAVE_SCHEME = "weave"
WEAVE_PRIVATE_SCHEME = "weave-private"

DICT_KEY_EDGE_NAME = "key"
LIST_INDEX_EDGE_NAME = "index"
OBJECT_ATTR_EDGE_NAME = "attr"
TABLE_ROW_ID_EDGE_NAME = "id"


def quote(s: str) -> str:
    return urllib_quote(s, safe="")


@dataclasses.dataclass
class InternalTableRef:
    project_id: str
    digest: str

    def uri(self) -> str:
        return f"{WEAVE_INTERNAL_SCHEME}:///{quote(self.project_id)}/table/{quote(self.digest)}"


@dataclasses.dataclass
class InternalObjectRef:
    project_id: str
    name: str
    version: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"{WEAVE_INTERNAL_SCHEME}:///{quote(self.project_id)}/object/{quote(self.name)}:{quote(self.version)}"
        if self.extra:
            u += "/" + "/".join([quote(e) for e in self.extra])
        return u


@dataclasses.dataclass
class InternalOpRef(InternalObjectRef):
    def uri(self) -> str:
        u = f"{WEAVE_INTERNAL_SCHEME}:///{quote(self.project_id)}/op/{quote(self.name)}:{quote(self.version)}"
        if self.extra:
            u += "/" + "/".join([quote(e) for e in self.extra])
        return u


@dataclasses.dataclass
class InternalCallRef:
    project_id: str
    id: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"{WEAVE_INTERNAL_SCHEME}:///{quote(self.project_id)}/call/{quote(self.id)}"
        if self.extra:
            u += "/" + "/".join([quote(e) for e in self.extra])
        return u


def parse_internal_uri(uri: str) -> Union[InternalObjectRef, InternalTableRef]:
    if uri.startswith(f"{WEAVE_INTERNAL_SCHEME}:///"):
        path = uri[len(f"{WEAVE_INTERNAL_SCHEME}:///") :]
        parts = path.split("/")
        if len(parts) < 2:
            raise ValueError(f"Invalid URI: {uri}")
        project_id_quoted, kind_quoted = parts[:2]

        project_id = unquote(project_id_quoted)
        kind = unquote(kind_quoted)

        remaining = parts[2:]
    elif uri.startswith(f"{WEAVE_SCHEME}:///"):
        path = uri[len(f"{WEAVE_SCHEME}:///") :]
        parts = path.split("/")
        if len(parts) < 3:
            raise ValueError(f"Invalid URI: {uri}")
        entity_quoted, project_quoted, kind_quoted = parts[:3]

        entity = unquote(entity_quoted)
        project = unquote(project_quoted)
        kind = unquote(kind_quoted)

        project_id = f"{entity}/{project}"
        remaining = parts[3:]
    else:
        raise ValueError(f"Invalid URI: {uri}")
    if kind == "table":
        return InternalTableRef(project_id=project_id, digest=unquote(remaining[0]))
    elif kind == "object":
        name_quoted, version_quoted = remaining[0].split(":")

        name = unquote(name_quoted)
        version = unquote(version_quoted)

        return InternalObjectRef(
            project_id=project_id,
            name=name,
            version=version,
            extra=[unquote(r) for r in remaining[1:]],
        )
    elif kind == "op":
        name_quoted, version_quoted = remaining[0].split(":")

        name = unquote(name_quoted)
        version = unquote(version_quoted)

        return InternalOpRef(
            project_id=project_id,
            name=name,
            version=version,
            extra=[unquote(r) for r in remaining[1:]],
        )
    else:
        raise ValueError(f"Unknown ref kind: {kind}")
