from typing import Any, Optional

from weave.trace.refs import ObjectRef, OpRef, parse_uri


class ObjectRefStrMatcher:
    def __init__(
        self,
        entity: Optional[str] = None,
        project: Optional[str] = None,
        kind: Optional[str] = None,
        name: Optional[str] = None,
        digest: Optional[str] = None,
        extra: Optional[list[str]] = None,
    ) -> None:
        self.entity = entity
        self.project = project
        self.kind = kind
        self.name = name
        self.digest = digest
        self.extra = extra

    def __eq__(self, other: Any) -> bool:
        other_ref = parse_uri(other)
        if not isinstance(other_ref, ObjectRef):
            return False
        if self.entity is not None:
            if self.entity != other_ref.entity:
                return False
        if self.project is not None:
            if self.project != other_ref.project:
                return False
        if self.kind is not None:
            if isinstance(other_ref, ObjectRef):
                other_kind = "object"
            elif isinstance(other_ref, OpRef):
                other_kind = "op"
            else:
                raise ValueError(f"Unknown kind: {other_ref}")
            if self.kind != other_kind:
                return False
        if self.name is not None:
            if self.name != other_ref.name:
                return False
        if self.digest is not None:
            if self.digest != other_ref.digest:
                return False
        if self.extra is not None:
            if self.extra != other_ref.extra:
                return False
        return True
