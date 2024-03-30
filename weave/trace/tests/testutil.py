from weave.trace.refs import parse_uri, ObjectRef, OpRef


class ObjectRefStrMatcher:
    def __init__(
        self, entity=None, project=None, kind=None, name=None, digest=None, extra=None
    ):
        self.entity = entity
        self.project = project
        self.kind = kind
        self.name = name
        self.digest = digest
        self.extra = extra

    def __eq__(self, other):
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
