"""Indexed word and phrase search over message content and occurrences."""

import re
from dataclasses import dataclass

from weave.shared.errors import InvalidRequest
from weave.trace_server.agents.constants import SEARCH_CONTENT_PREVIEW_CHARS
from weave.trace_server.agents.types import AgentSearchReq
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_builder import (
    _normalize_search_roles,
    _pagination_slots,
    add_time_filters,
)

_TOKEN = re.compile(r"[A-Za-z0-9\u0080-\U0010ffff]+")
_ORDER = "started_at DESC, span_id DESC, trace_id DESC, role DESC, content_digest DESC, created_at DESC"
_CONVERSATION_KEY = """if(conversation_id != '', concat('c:', conversation_id),
    if(trace_id != '', concat('t:', trace_id), concat('s:', span_id)))"""


@dataclass(frozen=True)
class MessageSearch:
    tokens: tuple[str, ...]
    phrases: tuple[str, ...]


def parse_message_search(query: str) -> MessageSearch:
    """Case-sensitive words and double-quoted token phrases; empty means retrieval."""
    if not query:
        return MessageSearch((), ())
    fragments: list[tuple[bool, str]] = []
    buffer: list[str] = []
    quoted = False
    position = 0
    while position < len(query):
        char = query[position]
        if (
            char == "\\"
            and position + 1 < len(query)
            and query[position + 1] in {'"', "\\"}
        ):
            buffer.append(query[position + 1])
            position += 2
            continue
        if char == '"':
            fragment = "".join(buffer)
            buffer.clear()
            if quoted and not _TOKEN.findall(fragment):
                raise InvalidRequest("A quoted phrase must contain at least one word")
            fragments.append((quoted, fragment))
            quoted = not quoted
        else:
            buffer.append(char)
        position += 1
    if quoted:
        raise InvalidRequest("Close the quoted phrase before searching")
    fragments.append((False, "".join(buffer)))
    tokens = tuple(
        dict.fromkeys(
            token for _, fragment in fragments for token in _TOKEN.findall(fragment)
        )
    )
    if not tokens:
        raise InvalidRequest("Enter at least one searchable word")
    return MessageSearch(
        tokens, tuple(fragment for is_phrase, fragment in fragments if is_phrase)
    )


def _search_key_filters(pb: ParamBuilder, req: AgentSearchReq) -> list[str]:
    """Filters on the occurrence replacement key, safe to apply before FINAL."""
    pid_slot = pb.add(req.project_id, param_type="String")
    conditions = [f"project_id = {pid_slot}"]
    if req.trace_id:
        trace_slot = pb.add(req.trace_id, param_type="String")
        conditions.append(f"trace_id = {trace_slot}")
    if req.roles:
        roles_slot = pb.add(
            _normalize_search_roles(req.roles), param_type="Array(String)"
        )
        conditions.append(f"role IN {roles_slot}")
    add_time_filters(
        conditions,
        pb,
        started_after=req.started_after,
        started_before=req.started_before,
        column="started_at",
    )
    return conditions


def _search_metadata_filters(pb: ParamBuilder, req: AgentSearchReq) -> list[str]:
    """Filters on mutable metadata, applied after resolving occurrence versions."""
    conditions = []
    for column in ("agent_name", "provider_name", "request_model", "conversation_id"):
        if value := getattr(req, column):
            slot = pb.add(value, param_type="String")
            conditions.append(f"{column} = {slot}")
    return conditions


def make_indexed_message_search_query(pb: ParamBuilder, req: AgentSearchReq) -> str:
    """Select the latest matching occurrences before hydrating a bounded page."""
    search = parse_message_search(req.query)
    key_filters = _search_key_filters(pb, req)
    metadata_filters = _search_metadata_filters(pb, req) + ["expire_at > now()"]
    project = pb.add(req.project_id, param_type="String")
    limit, offset = _pagination_slots(pb, req.limit, req.offset)
    predicates = []
    if search.tokens:
        tokens = pb.add(list(search.tokens), param_type="Array(String)")
        predicates.append(f"hasAllTokens(content, {tokens})")
    for phrase in search.phrases:
        slot = pb.add(phrase, param_type="String")
        predicates.append(
            "hasSubstr(tokens(content, 'splitByNonAlpha'), "
            f"tokens({slot}, 'splitByNonAlpha'))"
        )
    matching = ""
    collapse = ""
    if predicates:
        matching = f"""AND content_digest GLOBAL IN (
            SELECT content_digest FROM message_content
            WHERE project_id = {project} AND {" AND ".join(predicates)}
        )"""
        collapse = f"LIMIT 1 BY {_CONVERSATION_KEY}, role, content_digest"
    preview = (
        f"substring(content, 1, {SEARCH_CONTENT_PREVIEW_CHARS})"
        if req.truncate_content
        else "content"
    )
    return f"""
        WITH page AS MATERIALIZED (
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role, content_digest, started_at, created_at
            FROM message_occurrences FINAL
            PREWHERE {" AND ".join(key_filters)}
            {matching}
            WHERE {" AND ".join(metadata_filters)}
            ORDER BY {_ORDER}
            {collapse}
            LIMIT {limit} OFFSET {offset}
        )
        SELECT p.conversation_id AS conversation_id, p.conversation_name AS conversation_name,
               p.agent_name AS agent_name, p.span_id AS span_id, p.trace_id AS trace_id,
               p.role AS role, c.content AS content,
               lower(hex(p.content_digest)) AS content_digest, p.started_at AS started_at
        FROM page AS p
        GLOBAL INNER ALL JOIN (
            SELECT content_digest, any({preview}) AS content
            FROM message_content
            WHERE project_id = {project}
              AND content_digest GLOBAL IN (SELECT content_digest FROM page)
            GROUP BY content_digest
        ) AS c ON p.content_digest = c.content_digest
        ORDER BY p.started_at DESC, p.span_id DESC, p.trace_id DESC,
                 p.role DESC, p.content_digest DESC, p.created_at DESC
        SETTINGS enable_materialized_cte = 1, optimize_move_to_prewhere_if_final = 0,
                 do_not_merge_across_partitions_select_final = 1
    """
