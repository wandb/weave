import dataclasses
import urllib
from concurrent.futures import Future
from typing import Any, Optional, Union, cast

from ..trace_server import refs_internal

DICT_KEY_EDGE_NAME = refs_internal.DICT_KEY_EDGE_NAME
LIST_INDEX_EDGE_NAME = refs_internal.LIST_INDEX_EDGE_NAME
OBJECT_ATTR_EDGE_NAME = refs_internal.OBJECT_ATTR_EDGE_NAME
TABLE_ROW_ID_EDGE_NAME = refs_internal.TABLE_ROW_ID_EDGE_NAME


@dataclasses.dataclass(frozen=True)
class Ref:
    def uri(self) -> str:
        raise NotImplementedError

    def as_param_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class TableRef(Ref):
    entity: str
    project: str
    _digest: Union[str, Future[str]]
    _row_digests: Optional[Union[list[str], Future[list[str]]]] = None

    def as_param_dict(self) -> dict:
        return {
            "entity": self.entity,
            "project": self.project,
            "_digest": self._digest,
            "_row_digests": self._row_digests,
        }

    @property
    def digest(self) -> str:
        if isinstance(self._digest, Future):
            # Block until the Future resolves and store the result
            self.__dict__["_digest"] = self._digest.result()

        if not isinstance(self._digest, str):
            raise Exception(f"TableRef digest is not a string: {self._digest}")

        refs_internal.validate_no_slashes(self._digest, "digest")
        refs_internal.validate_no_colons(self._digest, "digest")

        return self._digest

    @property
    def row_digests(self) -> list[str]:
        if isinstance(self._row_digests, Future):
            # Block until the Future resolves and store the result
            self.__dict__["_row_digests"] = self._row_digests.result()

        if not isinstance(self._row_digests, list):
            raise Exception(f"TableRef row_digests is not a list: {self._row_digests}")

        return self._row_digests

    def __post_init__(self) -> None:
        if isinstance(self._digest, str):
            refs_internal.validate_no_slashes(self._digest, "digest")
            refs_internal.validate_no_colons(self._digest, "digest")

    def uri(self) -> str:
        return f"weave:///{self.entity}/{self.project}/table/{self.digest}"


@dataclasses.dataclass(frozen=True)
class RefWithExtra(Ref):
    def with_extra(self, extra: tuple[Union[str, Future[str]], ...]) -> "RefWithExtra":
        params = self.as_param_dict()
        params["_extra"] = self._extra + tuple(extra)  # type: ignore
        return self.__class__(**params)

    def with_key(self, key: str) -> "RefWithExtra":
        return self.with_extra((DICT_KEY_EDGE_NAME, key))

    def with_attr(self, attr: str) -> "RefWithExtra":
        return self.with_extra((OBJECT_ATTR_EDGE_NAME, attr))

    def with_index(self, index: int) -> "RefWithExtra":
        return self.with_extra((LIST_INDEX_EDGE_NAME, str(index)))

    def with_item(self, item_digest: Union[str, Future[str]]) -> "RefWithExtra":
        return self.with_extra((TABLE_ROW_ID_EDGE_NAME, item_digest))


@dataclasses.dataclass(frozen=True)
class ObjectRef(RefWithExtra):
    entity: str
    project: str
    name: str
    _digest: Union[str, Future[str]]
    _extra: tuple[Union[str, Future[str]], ...] = ()

    def as_param_dict(self) -> dict:
        return {
            "entity": self.entity,
            "project": self.project,
            "name": self.name,
            "_digest": self._digest,
            "_extra": self._extra,
        }

    @property
    def extra(self) -> tuple[str, ...]:
        if any(isinstance(e, Future) for e in self._extra):
            self.__dict__["_extra"] = tuple(
                e if isinstance(e, str) else e.result() for e in self._extra
            )
            refs_internal.validate_extra(list(self.extra))

        return cast(tuple[str, ...], self._extra)

    @property
    def digest(self) -> str:
        if isinstance(self._digest, Future):
            # Block until the Future resolves and store the result
            self.__dict__["_digest"] = self._digest.result()

        if not isinstance(self._digest, str):
            raise Exception(f"ObjectRef digest is not a string: {self._digest}")

        refs_internal.validate_no_slashes(self._digest, "digest")
        refs_internal.validate_no_colons(self._digest, "digest")

        return self._digest

    def __post_init__(self) -> None:
        if isinstance(self._digest, str):
            refs_internal.validate_no_slashes(self._digest, "digest")
            refs_internal.validate_no_colons(self._digest, "digest")

        refs_internal.validate_no_slashes(self.name, "name")
        refs_internal.validate_no_colons(self.name, "name")

    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/object/{self.name}:{self.digest}"
        if self.extra:
            u += "/" + "/".join(refs_internal.extra_value_quoter(e) for e in self.extra)
        return u

    def get(self) -> Any:
        # Move import here so that it only happens when the function is called.
        # This import is invalid in the trace server and represents a dependency
        # that should be removed.
        from weave.trace.client_context.weave_client import get_weave_client
        from weave.trace.weave_init import init_weave

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


@dataclasses.dataclass(frozen=True)
class OpRef(ObjectRef):
    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/op/{self.name}:{self.digest}"
        if self.extra:
            u += "/" + "/".join(refs_internal.extra_value_quoter(e) for e in self.extra)
        return u


@dataclasses.dataclass(frozen=True)
class CallRef(RefWithExtra):
    entity: str
    project: str
    id: str
    _extra: tuple[Union[str, Future[str]], ...] = ()

    def as_param_dict(self) -> dict:
        return {
            "entity": self.entity,
            "project": self.project,
            "id": self.id,
            "_extra": self._extra,
        }

    @property
    def extra(self) -> tuple[str, ...]:
        return tuple(e if isinstance(e, str) else e.result() for e in self._extra)

    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/call/{self.id}"
        if self._extra:
            u += "/" + "/".join(refs_internal.extra_value_quoter(e) for e in self.extra)
        return u


AnyRef = Union[ObjectRef, TableRef, CallRef, OpRef]


def parse_uri(uri: str) -> AnyRef:
    if not uri.startswith("weave:///"):
        raise ValueError(f"Invalid URI: {uri}")
    path = uri[len("weave:///") :]
    parts = path.split("/")
    if len(parts) < 3:
        raise ValueError(f"Invalid URI: {uri}")
    entity, project, kind = parts[:3]
    remaining = tuple(parts[3:])
    if kind == "table":
        return TableRef(entity=entity, project=project, _digest=remaining[0])
    extra = tuple(urllib.parse.unquote(r) for r in remaining[1:])
    if kind == "call":
        return CallRef(entity=entity, project=project, id=remaining[0], _extra=extra)
    elif kind == "object":
        name, version = remaining[0].split(":")
        return ObjectRef(
            entity=entity, project=project, name=name, _digest=version, _extra=extra
        )
    elif kind == "op":
        name, version = remaining[0].split(":")
        return OpRef(
            entity=entity, project=project, name=name, _digest=version, _extra=extra
        )
    else:
        raise ValueError(f"Unknown ref kind: {kind}")


def parse_op_uri(uri: str) -> OpRef:
    if not isinstance(parsed := parse_uri(uri), OpRef):
        raise ValueError(f"URI is not for an Op: {uri}")
    return parsed