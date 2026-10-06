"""Indexed message search. See agents/message-search.md for semantics and rollout."""

import re
from dataclasses import dataclass

from weave.shared.errors import InvalidRequest
from weave.trace_server.agents.constants import SEARCH_CONTENT_PREVIEW_CHARS
from weave.trace_server.agents.types import AgentSearchReq
from weave.trace_server.orm import ParamBuilder
from weave.trace_server.query_builder.agent_query_builder import _search_filter_sql

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


def make_indexed_message_search_query(
    pb: ParamBuilder, req: AgentSearchReq, *, stable_metadata: bool = False
) -> str:
    """Select a bounded occurrence page before hydrating content.

    stable_metadata skips FINAL only for text search in projects where every
    version of an occurrence has the same grouping/filter metadata. Structured
    retrieval always resolves the latest occurrence and preserves each span.
    """
    search = parse_message_search(req.query)
    filters = _search_filter_sql(pb, req, include_content=False)
    project = pb.add(req.project_id, param_type="String")
    limit = pb.add(req.limit, param_type="UInt64")
    offset = pb.add(req.offset, param_type="UInt64")
    predicates = []
    if search.tokens:
        tokens = pb.add(list(search.tokens), param_type="Array(String)")
        predicates.append(f"hasAllTokens(content, {tokens})")
    for phrase in search.phrases:
        slot = pb.add(phrase, param_type="String")
        predicates.append(f"hasPhrase(content, {slot})")
    matching = ""
    collapse = ""
    if predicates:
        matching = f"""AND content_digest GLOBAL IN (
            SELECT content_digest FROM message_content
            WHERE project_id = {project} AND {" AND ".join(predicates)}
        )"""
        collapse = f"LIMIT 1 BY {_CONVERSATION_KEY}, role, content_digest"
    final = "" if stable_metadata and search.tokens else " FINAL"
    preview = (
        f"substring(content, 1, {SEARCH_CONTENT_PREVIEW_CHARS})"
        if req.truncate_content
        else "content"
    )
    return f"""
        WITH page AS MATERIALIZED (
            SELECT conversation_id, conversation_name, agent_name,
                   span_id, trace_id, role, content_digest, started_at, created_at
            FROM message_occurrences{final}
            WHERE {filters.where} AND expire_at > now()
            {matching}
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
        SETTINGS enable_materialized_cte = 1, optimize_move_to_prewhere_if_final = 0
    """
