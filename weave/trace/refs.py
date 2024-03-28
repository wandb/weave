from typing import Union, Any
import dataclasses
from ..trace_server import refs_internal

KEY_EDGE_TYPE = refs_internal.KEY_EDGE_TYPE
INDEX_EDGE_TYPE = refs_internal.INDEX_EDGE_TYPE
ATTRIBUTE_EDGE_TYPE = refs_internal.ATTRIBUTE_EDGE_TYPE
ID_EDGE_TYPE = refs_internal.ID_EDGE_TYPE


@dataclasses.dataclass
class Ref:
    def uri(self) -> str:
        raise NotImplementedError


@dataclasses.dataclass
class TableRef(Ref):
    entity: str
    project: str
    digest: str

    def uri(self) -> str:
        return f"weave:///{self.entity}/{self.project}/table/{self.digest}"


@dataclasses.dataclass
class RefWithExtra(Ref):
    def with_extra(self, extra: list[str]) -> "RefWithExtra":
        params = dataclasses.asdict(self)
        params["extra"] = self.extra + extra  # type: ignore
        return self.__class__(**params)

    def with_key(self, key: str) -> "RefWithExtra":
        return self.with_extra([KEY_EDGE_TYPE, key])

    def with_attr(self, attr: str) -> "RefWithExtra":
        return self.with_extra([ATTRIBUTE_EDGE_TYPE, attr])

    def with_index(self, index: int) -> "RefWithExtra":
        return self.with_extra([INDEX_EDGE_TYPE, str(index)])

    def with_item(self, item_digest: str) -> "RefWithExtra":
        return self.with_extra([ID_EDGE_TYPE, f"{item_digest}"])


@dataclasses.dataclass
class ObjectRef(RefWithExtra):
    entity: str
    project: str
    name: str
    version: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/object/{self.name}:{self.version}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u

    def get(self) -> Any:
        # Move import here so that it only happens when the function is called.
        # This import is invalid in the trace server and represents a dependency
        # that should be removed.
        from weave.graph_client_context import require_graph_client

        gc = require_graph_client()
        return gc.get(self)

    def is_descended_from(self, potential_ancestor: "ObjectRef") -> bool:
        if self.entity != potential_ancestor.entity:
            return False
        if self.project != potential_ancestor.project:
            return False
        if self.name != potential_ancestor.name:
            return False
        if self.version != potential_ancestor.version:
            return False
        if len(self.extra) <= len(potential_ancestor.extra):
            return False
        return all(
            self.extra[i] == potential_ancestor.extra[i]
            for i in range(len(potential_ancestor.extra))
        )


@dataclasses.dataclass
class OpRef(ObjectRef):
    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/op/{self.name}:{self.version}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u


@dataclasses.dataclass
class CallRef(RefWithExtra):
    entity: str
    project: str
    id: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/call/{self.id}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u


def parse_uri(uri: str) -> Union[ObjectRef, TableRef]:
    if not uri.startswith("weave:///"):
        raise ValueError(f"Invalid URI: {uri}")
    path = uri[len("weave:///") :]
    parts = path.split("/")
    if len(parts) < 3:
        raise ValueError(f"Invalid URI: {uri}")
    entity, project, kind = parts[:3]
    remaining = parts[3:]
    if kind == "table":
        return TableRef(entity=entity, project=project, digest=remaining[0])
    elif kind == "object":
        name, version = remaining[0].split(":")
        return ObjectRef(
            entity=entity,
            project=project,
            name=name,
            version=version,
            extra=remaining[1:],
        )
    elif kind == "op":
        name, version = remaining[0].split(":")
        return OpRef(
            entity=entity,
            project=project,
            name=name,
            version=version,
            extra=remaining[1:],
        )
    else:
        raise ValueError(f"Unknown ref kind: {kind}")
