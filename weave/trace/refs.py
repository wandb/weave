from typing import Union, Any
import dataclasses

from weave.graph_client_context import require_graph_client

KEY_EDGE_TYPE = "key"
INDEX_EDGE_TYPE = "ndx"
ATTRIBUTE_EDGE_TYPE = "atr"
ID_EDGE_TYPE = "id"


@dataclasses.dataclass
class Ref:
    def uri(self) -> str:
        raise NotImplementedError

    def with_extra(self, extra: list[str]) -> "Ref":
        params = dataclasses.asdict(self)
        if not hasattr(self, "extra"):
            raise ValueError(f"Ref {self} does not have an extra field")
        params["extra"] = self.extra + extra
        return self.__class__(**params)

    def with_key(self, key: str) -> "Ref":
        return self.with_extra([KEY_EDGE_TYPE, key])

    def with_attr(self, attr: str) -> "Ref":
        return self.with_extra([ATTRIBUTE_EDGE_TYPE, attr])

    def with_index(self, index: int) -> "Ref":
        return self.with_extra([INDEX_EDGE_TYPE, str(index)])

    def with_item(self, item_digest: str) -> "Ref":
        return self.with_extra([ID_EDGE_TYPE, f"{item_digest}"])

    def __str__(self) -> str:
        return self.uri()


@dataclasses.dataclass
class TableRef(Ref):
    entity: str
    project: str
    digest: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/table/{self.digest}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u


@dataclasses.dataclass
class ObjectRef(Ref):
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
        gc = require_graph_client()
        return gc.get(self)


@dataclasses.dataclass
class OpRef(ObjectRef):
    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/op/{self.name}:{self.version}"
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
        return TableRef(
            entity=entity, project=project, digest=remaining[0], extra=remaining[1:]
        )
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


@dataclasses.dataclass
class CallRef(Ref):
    id: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"weave:///call/{self.id}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u
