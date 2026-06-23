from __future__ import annotations

import urllib
from concurrent.futures import Future
from dataclasses import asdict, dataclass, fields
from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from typing_extensions import Self

from weave.shared import refs_internal
from weave.shared.refs_internal import CallableProperty

if TYPE_CHECKING:
    from weave.trace_server.errors import ObjectDeletedError

DICT_KEY_EDGE_NAME = refs_internal.DICT_KEY_EDGE_NAME
LIST_INDEX_EDGE_NAME = refs_internal.LIST_INDEX_EDGE_NAME
OBJECT_ATTR_EDGE_NAME = refs_internal.OBJECT_ATTR_EDGE_NAME
TABLE_ROW_ID_EDGE_NAME = refs_internal.TABLE_ROW_ID_EDGE_NAME


class WeaveDigestError(ValueError):
    """Raised when a digest is invalid."""


@dataclass(frozen=True)
class Ref:
    @CallableProperty
    def uri(self) -> str:
        raise NotImplementedError

    def __str__(self) -> str:
        return self.uri

    def as_param_dict(self) -> dict:
        return asdict(self)

    def __deepcopy__(self, memo: dict) -> Self:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        res = self.__class__(**d)
        memo[id(self)] = res
        return res

    @staticmethod
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
        if kind in {"agent_turn", "agent_conversation", "agent_span"}:
            if len(remaining) != 1:
                raise ValueError(
                    f"Invalid URI: {uri}. {kind} ref must have exactly one path "
                    f"segment after the kind; got {len(remaining)}. "
                    f"IDs containing '/' must be URL-encoded."
                )
            if kind == "agent_turn":
                return AgentTurnRef(
                    entity=entity, project=project, trace_id=remaining[0]
                )
            if kind == "agent_conversation":
                return AgentConversationRef(
                    entity=entity,
                    project=project,
                    conversation_id=urllib.parse.unquote(remaining[0]),
                )
            return AgentSpanRef(entity=entity, project=project, span_id=remaining[0])
        extra = tuple(urllib.parse.unquote(r) for r in remaining[1:])
        if kind == "call":
            return CallRef(
                entity=entity, project=project, id=remaining[0], _extra=extra
            )
        elif kind == "object":
            name, version = parse_name_version(remaining[0])
            return ObjectRef(
                entity=entity, project=project, name=name, _digest=version, _extra=extra
            )
        elif kind == "op":
            name, version = parse_name_version(remaining[0])
            return OpRef(
                entity=entity, project=project, name=name, _digest=version, _extra=extra
            )
        else:
            raise ValueError(f"Unknown ref kind: {kind}")

    @staticmethod
    def maybe_parse_uri(s: str) -> AnyRef | None:
        try:
            return Ref.parse_uri(s)
        except ValueError:
            return None


@dataclass(frozen=True)
class TableRef(Ref):
    entity: str
    project: str
    _digest: str | Future[str]
    _row_digests: list[str] | Future[list[str]] | None = None

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
            raise WeaveDigestError(f"TableRef digest is not a string: {self._digest}")

        refs_internal.validate_no_slashes(self._digest, "digest")
        refs_internal.validate_no_colons(self._digest, "digest")

        return self._digest

    @property
    def row_digests(self) -> list[str]:
        if isinstance(self._row_digests, Future):
            # Block until the Future resolves and store the result
            self.__dict__["_row_digests"] = self._row_digests.result()

        if not isinstance(self._row_digests, list):
            raise WeaveDigestError(
                f"TableRef row_digests is not a list: {self._row_digests}"
            )

        return self._row_digests

    @property
    def project_id(self) -> str:
        return f"{self.entity}/{self.project}"

    def __post_init__(self) -> None:
        if isinstance(self._digest, str):
            refs_internal.validate_no_slashes(self._digest, "digest")
            refs_internal.validate_no_colons(self._digest, "digest")

    @CallableProperty
    def uri(self) -> str:
        return f"weave:///{self.entity}/{self.project}/table/{self.digest}"

    @staticmethod
    def parse_uri(uri: str) -> TableRef:
        if not isinstance(parsed := Ref.parse_uri(uri), TableRef):
            raise TypeError(f"URI is not for a Table: {uri}")
        return parsed


@dataclass(frozen=True)
class RefWithExtra(Ref):
    def with_extra(self, extra: tuple[str | Future[str], ...]) -> Self:
        params = self.as_param_dict()
        params["_extra"] = self._extra + tuple(extra)  # type: ignore
        return self.__class__(**params)

    def with_key(self, key: str) -> Self:
        return self.with_extra((DICT_KEY_EDGE_NAME, key))

    def with_attr(self, attr: str) -> Self:
        return self.with_extra((OBJECT_ATTR_EDGE_NAME, attr))

    def with_index(self, index: int) -> Self:
        return self.with_extra((LIST_INDEX_EDGE_NAME, str(index)))

    def with_item(self, item_digest: str | Future[str]) -> Self:
        return self.with_extra((TABLE_ROW_ID_EDGE_NAME, item_digest))


@dataclass(frozen=True)
class ObjectRef(RefWithExtra):
    entity: str
    project: str
    name: str
    _digest: str | Future[str]
    _extra: tuple[str | Future[str], ...] = ()

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
            raise WeaveDigestError(f"ObjectRef digest is not a string: {self._digest}")

        refs_internal.validate_no_slashes(self._digest, "digest")
        refs_internal.validate_no_colons(self._digest, "digest")

        return self._digest

    @property
    def is_digest_resolved(self) -> bool:
        return not isinstance(self._digest, Future)

    def __post_init__(self) -> None:
        if isinstance(self._digest, str):
            refs_internal.validate_no_slashes(self._digest, "digest")
            refs_internal.validate_no_colons(self._digest, "digest")

        refs_internal.validate_no_slashes(self.name, "name")
        refs_internal.validate_no_colons(self.name, "name")

    @CallableProperty
    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/object/{self.name}:{self.digest}"
        if self.extra:
            u += "/" + "/".join(refs_internal.extra_value_quoter(e) for e in self.extra)
        return u

    def get(self, *, objectify: bool = True) -> Any:
        # Move import here so that it only happens when the function is called.
        # This import is invalid in the trace server and represents a dependency
        # that should be removed.
        from weave.trace.context.weave_client_context import (
            get_weave_client,
            set_weave_client_global,
        )
        from weave.trace.weave_init import init_weave

        gc = get_weave_client()
        if gc is not None:
            return gc.get(self, objectify=objectify)

        # Special case: If the user is attempting to fetch an object but has not
        # yet initialized the client, we can initialize a client to
        # fetch the object. It is critical to reset the client after fetching the
        # object to avoid any side effects in user code.

        client = init_weave(
            f"{self.entity}/{self.project}", ensure_project_exists=False
        )
        try:
            res = client.get(self, objectify=objectify)
        finally:
            set_weave_client_global(None)
        return res

    def is_descended_from(self, potential_ancestor: ObjectRef) -> bool:
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

    def delete(self) -> None:
        from weave.trace.context.weave_client_context import get_weave_client

        gc = get_weave_client()
        if gc is not None:
            gc.delete_object_version(self)

    @staticmethod
    def parse_uri(uri: str) -> ObjectRef:
        if not isinstance(parsed := Ref.parse_uri(uri), ObjectRef):
            raise TypeError(f"URI is not for an Object: {uri}")
        return parsed


@dataclass(frozen=True)
class OpRef(ObjectRef):
    @CallableProperty
    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/op/{self.name}:{self.digest}"
        if self.extra:
            u += "/" + "/".join(refs_internal.extra_value_quoter(e) for e in self.extra)
        return u

    def delete(self) -> None:
        from weave.trace.context.weave_client_context import get_weave_client

        gc = get_weave_client()
        if gc is not None:
            gc.delete_op_version(self)

    @staticmethod
    def parse_uri(uri: str) -> OpRef:
        if not isinstance(parsed := Ref.parse_uri(uri), OpRef):
            raise TypeError(f"URI is not for an Op: {uri}")
        return parsed


@dataclass(frozen=True)
class CallRef(RefWithExtra):
    entity: str
    project: str
    id: str
    _extra: tuple[str | Future[str], ...] = ()

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

    @CallableProperty
    def uri(self) -> str:
        u = f"weave:///{self.entity}/{self.project}/call/{self.id}"
        if self._extra:
            u += "/" + "/".join(refs_internal.extra_value_quoter(e) for e in self.extra)
        return u

    @staticmethod
    def parse_uri(uri: str) -> CallRef:
        if not isinstance(parsed := Ref.parse_uri(uri), CallRef):
            raise TypeError(f"URI is not for a Call: {uri}")
        return parsed


@dataclass(frozen=True)
class AgentTurnRef(Ref):
    """Stable URI pointing at one turn in the Agents view.

    A turn is a single trace's chat trajectory: one user prompt, the
    assistant's complete response, and every tool call or sub-agent
    invocation in between. Use this ref when you have a `trace_id` and
    want a URI that the Weave UI (or the `agent_traces_chat` API) can
    resolve back to a turn.

    URI grammar: `weave:///{entity}/{project}/agent_turn/{trace_id}`.

    Attributes:
        entity: W&B entity (team or username) that owns the project.
        project: Project name within the entity.
        trace_id: OTel trace ID that identifies the turn.

    Examples:
        >>> ref = AgentTurnRef(entity="acme", project="bot", trace_id="t1")
        >>> ref.uri
        'weave:///acme/bot/agent_turn/t1'
        >>> AgentTurnRef.parse_uri(ref.uri) == ref
        True
    """

    entity: str
    project: str
    trace_id: str

    @CallableProperty
    def uri(self) -> str:
        return f"weave:///{self.entity}/{self.project}/agent_turn/{self.trace_id}"

    @staticmethod
    def parse_uri(uri: str) -> AgentTurnRef:
        """Parse a Weave URI into an `AgentTurnRef`.

        Args:
            uri: A `weave:///` URI produced by `AgentTurnRef.uri`.

        Returns:
            AgentTurnRef: Parsed ref.

        Raises:
            TypeError: When `uri` is valid Weave syntax but points at a
                non-turn ref kind (e.g. a call or object ref).
            ValueError: When `uri` doesn't match the Weave URI grammar.
        """
        if not isinstance(parsed := Ref.parse_uri(uri), AgentTurnRef):
            raise TypeError(f"URI is not for an AgentTurn: {uri}")
        return parsed


@dataclass(frozen=True)
class AgentConversationRef(Ref):
    """Stable URI pointing at one conversation in the Agents view.

    A conversation is the ordered set of turns sharing a single
    `gen_ai.conversation.id`. Use this ref to link to the multi-turn
    chat view served by `agent_conversation_chat`.

    URI grammar:
    `weave:///{entity}/{project}/agent_conversation/{encoded_conversation_id}`.

    Note:
        `conversation_id` is URL-quoted in the URI so IDs containing
        `/` or other reserved characters round-trip safely. The ref
        itself stores the decoded value.

    Attributes:
        entity: W&B entity (team or username) that owns the project.
        project: Project name within the entity.
        conversation_id: Conversation identifier extracted from
            `gen_ai.conversation.id` on the producing spans.

    Examples:
        >>> ref = AgentConversationRef(
        ...     entity="acme", project="bot", conversation_id="sess/42"
        ... )
        >>> ref.uri
        'weave:///acme/bot/agent_conversation/sess%2F42'
        >>> AgentConversationRef.parse_uri(ref.uri).conversation_id
        'sess/42'
    """

    entity: str
    project: str
    conversation_id: str

    @CallableProperty
    def uri(self) -> str:
        encoded = refs_internal.extra_value_quoter(self.conversation_id)
        return f"weave:///{self.entity}/{self.project}/agent_conversation/{encoded}"

    @staticmethod
    def parse_uri(uri: str) -> AgentConversationRef:
        """Parse a Weave URI into an `AgentConversationRef`.

        The encoded `conversation_id` segment is URL-decoded during
        parsing, so the resulting `conversation_id` matches the value
        emitted by the producing instrumentation.

        Args:
            uri: A `weave:///` URI produced by
                `AgentConversationRef.uri`.

        Returns:
            AgentConversationRef: Parsed ref.

        Raises:
            TypeError: When `uri` is valid Weave syntax but points at a
                non-conversation ref kind.
            ValueError: When `uri` doesn't match the Weave URI grammar.
        """
        if not isinstance(parsed := Ref.parse_uri(uri), AgentConversationRef):
            raise TypeError(f"URI is not for an AgentConversation: {uri}")
        return parsed


@dataclass(frozen=True)
class AgentSpanRef(Ref):
    """Stable URI pointing at one span in the Agents view.

    A span is a single OTel GenAI span: an agent invocation, an LLM
    call, a tool execution, or another GenAI event. Use this ref when
    you want a URI that resolves back to a specific span row inside an
    agent trace.

    URI grammar: `weave:///{entity}/{project}/agent_span/{span_id}`.

    Attributes:
        entity: W&B entity (team or username) that owns the project.
        project: Project name within the entity.
        span_id: OTel span ID.

    Examples:
        >>> ref = AgentSpanRef(entity="acme", project="bot", span_id="s9")
        >>> ref.uri
        'weave:///acme/bot/agent_span/s9'
    """

    entity: str
    project: str
    span_id: str

    @CallableProperty
    def uri(self) -> str:
        return f"weave:///{self.entity}/{self.project}/agent_span/{self.span_id}"

    @staticmethod
    def parse_uri(uri: str) -> AgentSpanRef:
        """Parse a Weave URI into an `AgentSpanRef`.

        Args:
            uri: A `weave:///` URI produced by `AgentSpanRef.uri`.

        Returns:
            AgentSpanRef: Parsed ref.

        Raises:
            TypeError: When `uri` is valid Weave syntax but points at a
                non-span ref kind.
            ValueError: When `uri` doesn't match the Weave URI grammar.
        """
        if not isinstance(parsed := Ref.parse_uri(uri), AgentSpanRef):
            raise TypeError(f"URI is not for an AgentSpan: {uri}")
        return parsed


@dataclass(frozen=True)
class DeletedRef(Ref):
    ref: Ref
    deleted_at: datetime
    error: ObjectDeletedError

    def __repr__(self) -> str:
        return f"<DeletedRef {self.uri}>"

    @CallableProperty
    def uri(self) -> str:
        return self.ref.uri


AnyRef = (
    ObjectRef
    | TableRef
    | CallRef
    | OpRef
    | AgentTurnRef
    | AgentConversationRef
    | AgentSpanRef
)


def parse_name_version(name_version: str) -> tuple[str, str]:
    if ":" in name_version:
        name, version = name_version.rsplit(":", maxsplit=1)
        return name, version
    return name_version, "latest"
