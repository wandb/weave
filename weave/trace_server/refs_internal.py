# This file contains the definition for "Internal" weave refs. These should never be
# exposed to the user and should only be used internally by the weave-trace service.
# Specifically, the user-space operates on plain-text `entity/project` scopes. While
# internally, we operate on internal `project_id`s scopes. At rest, and in the database,
# we store the internal `project_id`. However, over the wire, we use the plain-text. Practically,
# the trace interface should only ever operate on internal refs.

import dataclasses
from typing import Union

WEAVE_INTERNAL_SCHEME = "weave-trace-internal"
WEAVE_SCHEME = "weave"

DICT_KEY_EDGE_NAME = "key"
LIST_INDEX_EDGE_NAME = "index"
OBJECT_ATTR_EDGE_NAME = "attr"
TABLE_ROW_ID_EDGE_NAME = "id"


@dataclasses.dataclass
class InternalTableRef:
    project_id: str
    digest: str

    def uri(self) -> str:
        return f"{WEAVE_INTERNAL_SCHEME}:///{self.project_id}/table/{self.digest}"


@dataclasses.dataclass
class InternalObjectRef:
    project_id: str
    name: str
    version: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"{WEAVE_INTERNAL_SCHEME}:///{self.project_id}/object/{self.name}:{self.version}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u


@dataclasses.dataclass
class InternalOpRef(InternalObjectRef):
    def uri(self) -> str:
        u = f"{WEAVE_INTERNAL_SCHEME}:///{self.project_id}/op/{self.name}:{self.version}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u


@dataclasses.dataclass
class InternalCallRef:
    project_id: str
    id: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"{WEAVE_INTERNAL_SCHEME}:///{self.project_id}/call/{self.id}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u


def parse_internal_uri(uri: str) -> Union[InternalObjectRef, InternalTableRef]:
    if uri.startswith(f"{WEAVE_INTERNAL_SCHEME}:///"):
        path = uri[len(f"{WEAVE_INTERNAL_SCHEME}:///") :]
        parts = path.split("/")
        if len(parts) < 2:
            raise ValueError(f"Invalid URI: {uri}")
        project_id, kind = parts[:2]
        remaining = parts[2:]
    elif uri.startswith(f"{WEAVE_SCHEME}:///"):
        path = uri[len(f"{WEAVE_SCHEME}:///") :]
        parts = path.split("/")
        if len(parts) < 3:
            raise ValueError(f"Invalid URI: {uri}")
        entity, project, kind = parts[:3]
        project_id = f"{entity}/{project}"
        remaining = parts[3:]
    else:
        raise ValueError(f"Invalid URI: {uri}")
    if kind == "table":
        return InternalTableRef(project_id=project_id, digest=remaining[0])
    elif kind == "object":
        name, version = remaining[0].split(":")
        return InternalObjectRef(
            project_id=project_id,
            name=name,
            version=version,
            extra=remaining[1:],
        )
    elif kind == "op":
        name, version = remaining[0].split(":")
        return InternalOpRef(
            project_id=project_id,
            name=name,
            version=version,
            extra=remaining[1:],
        )
    else:
        raise ValueError(f"Unknown ref kind: {kind}")
