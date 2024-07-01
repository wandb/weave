import dataclasses
from typing import Any, Union

from ..trace_server import refs_internal

DICT_KEY_EDGE_NAME = refs_internal.DICT_KEY_EDGE_NAME
LIST_INDEX_EDGE_NAME = refs_internal.LIST_INDEX_EDGE_NAME
OBJECT_ATTR_EDGE_NAME = refs_internal.OBJECT_ATTR_EDGE_NAME
TABLE_ROW_ID_EDGE_NAME = refs_internal.TABLE_ROW_ID_EDGE_NAME


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
        return self.with_extra([DICT_KEY_EDGE_NAME, key])

    def with_attr(self, attr: str) -> "RefWithExtra":
        return self.with_extra([OBJECT_ATTR_EDGE_NAME, attr])

    def with_index(self, index: int) -> "RefWithExtra":
        return self.with_extra([LIST_INDEX_EDGE_NAME, str(index)])

    def with_item(self, item_digest: str) -> "RefWithExtra":
        return self.with_extra([TABLE_ROW_ID_EDGE_NAME, f"{item_digest}"])


@dataclasses.dataclass
class ObjectRef(RefWithExtra):
    entity: str
    project: str
    name: str
    digest: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/object/{self.name}:{self.digest}"
        if self.extra:
            u += "/" + "/".join(self.extra)
        return u

    def get(self) -> Any:
        # Move import here so that it only happens when the function is called.
        # This import is invalid in the trace server and represents a dependency
        # that should be removed.
        from weave.client_context.weave_client import get_weave_client
        from weave.weave_init import init_weave

        gc = get_weave_client()
        if gc is not None:
            return gc.get(self)

        # Special case: If the user is attempting to fetch an object but has not
        # yet initialized the client, we can initialize a client to
        # fetch the object. It is critical to reset the client after fetching the
        # object to avoid any side effects in user code.
        if gc is None:
            init_client = init_weave(
                f"{self.entity}/{self.project}", ensure_project_exists=False
            )
            try:
                res = init_client.client.get(self)
            finally:
                init_client.reset()
            return res

    def is_descended_from(self, potential_ancestor: "ObjectRef") -> bool:
        if self.entity != potential_ancestor.entity:
            return False
        if self.project != potential_ancestor.project:
            return False
        if self.name != potential_ancestor.name:
            return False
        if self.digest != potential_ancestor.digest:
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
        u = f"weave:///{self.entity}/{self.project}/op/{self.name}:{self.digest}"
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


AnyRef = Union[ObjectRef, TableRef, CallRef]


def parse_uri(uri: str) -> AnyRef:
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
    elif kind == "call":
        return CallRef(
            entity=entity, project=project, id=remaining[0], extra=remaining[1:]
        )
    elif kind == "object":
        name, version = remaining[0].split(":")
        return ObjectRef(
            entity=entity,
            project=project,
            name=name,
            digest=version,
            extra=remaining[1:],
        )
    elif kind == "op":
        name, version = remaining[0].split(":")
        return OpRef(
            entity=entity,
            project=project,
            name=name,
            digest=version,
            extra=remaining[1:],
        )
    else:
        raise ValueError(f"Unknown ref kind: {kind}")
