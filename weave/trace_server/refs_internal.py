# This file contains the definition for "Internal" weave refs. These should never be
# exposed to the user and should only be used internally by the weave-trace service.
# Specifically, the user-space operates on plain-text `entity/project` scopes. While
# internally, we operate on internal `project_id`s scopes. At rest, and in the database,
# we store the internal `project_id`. However, over the wire, we use the plain-text. Practically,
# the trace interface should only ever operate on internal refs.
import dataclasses
import urllib
from typing import Any, Union

WEAVE_INTERNAL_SCHEME = "weave-trace-internal"
WEAVE_SCHEME = "weave"
WEAVE_PRIVATE_SCHEME = "weave-private"
ARTIFACT_REF_SCHEME = "wandb-artifact"

DICT_KEY_EDGE_NAME = "key"
LIST_INDEX_EDGE_NAME = "index"
OBJECT_ATTR_EDGE_NAME = "attr"
TABLE_ROW_ID_EDGE_NAME = "id"

valid_edge_names = (
    DICT_KEY_EDGE_NAME,
    LIST_INDEX_EDGE_NAME,
    OBJECT_ATTR_EDGE_NAME,
    TABLE_ROW_ID_EDGE_NAME,
)


class InvalidInternalRef(ValueError):
    pass


def extra_value_quoter(s: str) -> str:
    # Here, we encode all non alpha-numerics or `_.-~`.
    return urllib.parse.quote(s, safe="")


def validate_extra(extra: list[str]) -> None:
    """The `extra` path is always a series of `edge_name`/`edge_value` pairs.
    For example: `attr/attr_name/index/0`. The `edge_name` is one of the
    following: `key`, `index`, `attr`, `id`. The `edge_value` is a string
    that corresponds to the edge name. In the case of `attr` and `key`, the
    edge value is purely user-defined and can be any string.
    """
    if len(extra) % 2 != 0:
        raise InvalidInternalRef("Extra fields must be key-value pairs.")

    for i, e in enumerate(extra):
        if i % 2 == 0:
            # Here we are in the edge name position
            if e not in (
                DICT_KEY_EDGE_NAME,
                LIST_INDEX_EDGE_NAME,
                OBJECT_ATTR_EDGE_NAME,
                TABLE_ROW_ID_EDGE_NAME,
            ):
                raise InvalidInternalRef(
                    f"Invalid extra edge name at index {i}: {extra}"
                )
        else:
            # Here we are in the edge value position
            # There is only a single rule here:
            if extra[i - 1] == LIST_INDEX_EDGE_NAME:
                try:
                    int(e)
                except ValueError:
                    raise InvalidInternalRef(
                        f"Invalid list edge value at index {i}: {extra}"
                    )
            pass


def validate_no_slashes(s: str, field_name: str) -> None:
    if "/" in s:
        raise InvalidInternalRef(f"{field_name} cannot contain '/'")


def validate_no_colons(s: str, field_name: str) -> None:
    if ":" in s:
        raise InvalidInternalRef(f"{field_name} cannot contain ':'")


@dataclasses.dataclass(frozen=True)
class InternalTableRef:
    project_id: str
    digest: str

    def __post_init__(self) -> None:
        validate_no_slashes(self.project_id, "project_id")
        validate_no_slashes(self.digest, "digest")

    def uri(self) -> str:
        return f"{WEAVE_INTERNAL_SCHEME}:///{self.project_id}/table/{self.digest}"


@dataclasses.dataclass(frozen=True)
class InternalObjectRef:
    project_id: str
    name: str
    version: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def __post_init__(self) -> None:
        validate_no_slashes(self.project_id, "project_id")
        validate_no_slashes(self.version, "version")
        validate_no_colons(self.version, "version")
        validate_extra(self.extra)
        validate_no_slashes(self.name, "name")
        validate_no_colons(self.name, "name")

    def uri(self) -> str:
        u = f"{WEAVE_INTERNAL_SCHEME}:///{self.project_id}/object/{self.name}:{self.version}"
        if self.extra:
            u += "/" + "/".join(extra_value_quoter(e) for e in self.extra)
        return u


@dataclasses.dataclass(frozen=True)
class InternalOpRef(InternalObjectRef):
    def uri(self) -> str:
        u = f"{WEAVE_INTERNAL_SCHEME}:///{self.project_id}/op/{self.name}:{self.version}"
        if self.extra:
            u += "/" + "/".join(extra_value_quoter(e) for e in self.extra)
        return u


@dataclasses.dataclass(frozen=True)
class InternalCallRef:
    project_id: str
    id: str
    extra: list[str] = dataclasses.field(default_factory=list)

    def __post_init__(self) -> None:
        validate_no_slashes(self.project_id, "project_id")
        validate_no_slashes(self.id, "id")
        # Note: we don't actually support extra fields for calls, but when
        # we do, we need to add edge names to the known list
        validate_extra(self.extra)

    def uri(self) -> str:
        u = f"{WEAVE_INTERNAL_SCHEME}:///{self.project_id}/call/{self.id}"
        if self.extra:
            u += "/" + "/".join(extra_value_quoter(e) for e in self.extra)
        return u


@dataclasses.dataclass(frozen=True)
class InternalArtifactRef:
    project_id: str
    id: str

    def __post_init__(self) -> None:
        # not validating no slashes in project_id because we aren't converting to internal project_id
        validate_no_slashes(self.id, "id")

    def uri(self) -> str:
        u = f"{ARTIFACT_REF_SCHEME}:///{self.project_id}/{self.id}"
        return u


InternalRef = Union[
    InternalObjectRef, InternalTableRef, InternalCallRef, InternalArtifactRef
]


def parse_internal_uri(
    uri: str,
) -> InternalRef:
    if uri.startswith(f"{WEAVE_INTERNAL_SCHEME}:///"):
        path = uri[len(f"{WEAVE_INTERNAL_SCHEME}:///") :]
        parts = path.split("/")
        if len(parts) < 2:
            raise InvalidInternalRef(f"Invalid URI: {uri}. Must have at least 2 parts")
        project_id, kind = parts[:2]
        remaining = parts[2:]
    elif uri.startswith(f"{WEAVE_SCHEME}:///"):
        path = uri[len(f"{WEAVE_SCHEME}:///") :]
        parts = path.split("/")
        if len(parts) < 3:
            raise InvalidInternalRef(f"Invalid URI: {uri}. Must have at least 3 parts")
        entity, project, kind = parts[:3]
        project_id = f"{entity}/{project}"
        remaining = parts[3:]
    elif uri.startswith(f"{ARTIFACT_REF_SCHEME}:///"):
        path = uri[len(f"{ARTIFACT_REF_SCHEME}:///") :]
        parts = path.split("/")
        if len(parts) < 3:
            raise InvalidInternalRef(f"Invalid URI: {uri}. Must have at least 3 parts")
        entity, project = parts[:2]
        project_id = f"{entity}/{project}"
        kind = "artifact"
        remaining = parts[2:]
    else:
        raise InvalidInternalRef(
            f"Invalid URI: {uri}. Must start with {WEAVE_INTERNAL_SCHEME}:/// or {WEAVE_SCHEME}:/// "
            f"or {ARTIFACT_REF_SCHEME}:///"
        )
    if kind == "table":
        return InternalTableRef(project_id=project_id, digest=remaining[0])
    elif kind == "object":
        name, version, extra = _parse_remaining(remaining)
        return InternalObjectRef(
            project_id=project_id,
            name=name,
            version=version,
            extra=extra,
        )
    elif kind == "op":
        name, version, extra = _parse_remaining(remaining)
        return InternalOpRef(
            project_id=project_id,
            name=name,
            version=version,
            extra=extra,
        )
    elif kind == "call":
        id_ = remaining[0]
        return InternalCallRef(project_id=project_id, id=id_)
    elif kind == "artifact":
        id_ = remaining[0]
        return InternalArtifactRef(project_id=project_id, id=id_)
    else:
        raise InvalidInternalRef(f"Unknown ref kind: {kind}")


def _parse_remaining(remaining: list[str]) -> tuple[str, str, list[str]]:
    """`remaining` refers to everything after `object` or `op` in the ref.
    It is expected to be pre-split by slashes into parts. The return
    is a tuple of name, version, and extra parts, properly unquoted.
    """
    name, version = remaining[0].split(":")
    extra = remaining[1:]
    if len(extra) == 1 and extra[0] == "":
        extra = []
    else:
        extra = [urllib.parse.unquote(r) for r in extra]

    return name, version, extra


def string_will_be_interpreted_as_ref(s: str) -> bool:
    return s.startswith(f"{WEAVE_INTERNAL_SCHEME}:///") or s.startswith(
        f"{WEAVE_SCHEME}:///"
    )


def any_will_be_interpreted_as_ref_str(val: Any) -> bool:
    return isinstance(val, str) and string_will_be_interpreted_as_ref(val)
