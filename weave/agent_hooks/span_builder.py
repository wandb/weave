"""OTel span lifecycle manager for agent session tracing.

Translates normalized ``AgentHookEvent`` objects into OTel spans that follow
the GenAI semantic conventions, so Cursor/Claude Code/Codex sessions appear
correctly in the Weave traces, agents, and conversations views.

Span hierarchy produced per turn (each turn is a separate trace)::

    invoke_agent cursor-agent          (user_prompt → stop)
    ├── execute_tool Read              (tool_use_start → tool_use_end)
    ├── execute_tool bash              (shell_exec — instant)
    ├── invoke_agent subagent-type     (subagent_start → subagent_stop)
    └── ...

All turns within a conversation share ``gen_ai.conversation.id`` so they
can be stitched together in the Conversations view.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import sqlite3
import sys
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Span

from weave.agent_hooks.events import AgentHookEvent

logger = logging.getLogger(__name__)

_TOOL_OUTPUT_TRUNCATE = 4096
_TRANSCRIPT_TRUNCATE = 32_768
_CONTENT_REFS_ATTR = "weave.content_refs"
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)


_MODEL_PROVIDER_PREFIXES: dict[str, str] = {
    "claude": "anthropic",
    "gpt": "openai",
    "o1": "openai",
    "o3": "openai",
    "o4": "openai",
    "chatgpt": "openai",
    "gemini": "google",
    "gemma": "google",
}


def _provider_from_model(model: str) -> str:
    """Infer the LLM provider from a model name prefix."""
    if not model:
        return ""
    m = model.lower()
    for prefix, provider in _MODEL_PROVIDER_PREFIXES.items():
        if m.startswith(prefix):
            return provider
    return ""


def _looks_like_uuid(s: str) -> bool:
    """Return True if *s* is a UUID-formatted string."""
    return bool(_UUID_RE.match(s))


def _cursor_global_state_vscdb_path() -> Path:
    """Return the path to Cursor's global ``state.vscdb`` for this OS."""
    home = Path.home()
    if sys.platform == "darwin":
        return (
            home
            / "Library"
            / "Application Support"
            / "Cursor"
            / "User"
            / "globalStorage"
            / "state.vscdb"
        )
    if sys.platform == "win32":
        return home / "AppData" / "Roaming" / "Cursor" / "User" / "globalStorage" / "state.vscdb"
    return home / ".config" / "Cursor" / "User" / "globalStorage" / "state.vscdb"


def _composer_lookup_ids(
    conversation_id: str,
    transcript_path: str = "",
    extra_ids: tuple[str, ...] = (),
) -> list[str]:
    """Return distinct candidate ids used in ``composerData:<id>`` keys.

    Cursor versions differ on whether hooks send ``composerId``, ``chatId``,
    or only the transcript filename stem — we try every hint.
    """
    out: list[str] = []

    def add(s: str) -> None:
        s = (s or "").strip()
        if s and s not in out:
            out.append(s)

    add(conversation_id)
    for x in extra_ids:
        add(str(x))
    if transcript_path:
        stem = Path(transcript_path).name
        for suffix in (".jsonl", ".json"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        add(stem)
    for cid in list(out):
        if _looks_like_uuid(cid):
            add(cid.lower())
            add(cid.upper())
    return out


def _ids_match(a: str, b: str) -> bool:
    """Return True if *a* and *b* refer to the same Cursor id."""
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if _looks_like_uuid(a) and _looks_like_uuid(b) and a.lower() == b.lower():
        return True
    return False


def _name_from_composer_json(data: Any, match_id: str) -> str:
    """Extract a display title from a composer JSON blob."""
    if not isinstance(data, dict):
        return ""
    ac = data.get("allComposers")
    if isinstance(ac, list):
        for c in ac:
            if not isinstance(c, dict):
                continue
            cids = (
                str(c.get("composerId") or ""),
                str(c.get("composer_id") or ""),
                str(c.get("chatId") or ""),
                str(c.get("conversationId") or ""),
                str(c.get("sessionId") or ""),
            )
            if any(x and _ids_match(x, match_id) for x in cids):
                n = c.get("name", "")
                if isinstance(n, str) and n.strip():
                    return n.strip()
        return ""
    n = data.get("name", "")
    if isinstance(n, str) and n.strip():
        return n.strip()
    return ""


def _read_kv_value(conn: sqlite3.Connection, table: str, key: str) -> str | None:
    """Read a single key from *table* if the table exists."""
    try:
        row = conn.execute(f"SELECT value FROM {table} WHERE key = ?", (key,)).fetchone()
    except sqlite3.Error:
        return None
    if not row:
        return None
    return row[0]


def _read_cursor_session_name(
    conversation_id: str,
    *,
    transcript_path: str = "",
    extra_ids: tuple[str, ...] = (),
) -> str:
    """Read the LLM-generated session title from Cursor's local SQLite DB.

    Cursor stores composer metadata in the global ``state.vscdb``.  Newer
    builds may use ``composerData:<composerId>`` rows, ``allComposers``
    index blobs, or ``ItemTable`` instead of ``cursorDiskKV``.  Titles are
    often written *after* the model responds, so callers should re-query on
    ``afterAgentResponse`` / ``stop``, not only on ``beforeSubmitPrompt``.

    Args:
        conversation_id: Primary id from hook payloads (``conversation_id``).
        transcript_path: Optional path whose basename may match ``composerId``.
        extra_ids: Optional ids from the raw payload (e.g. ``composerId``).

    Returns:
        The session title, or empty string on any failure.
    """
    db_path = _cursor_global_state_vscdb_path()
    if not db_path.exists():
        return ""
    candidates = _composer_lookup_ids(
        conversation_id,
        transcript_path=transcript_path,
        extra_ids=extra_ids,
    )
    if not candidates:
        return ""
    try:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=3)
    except sqlite3.Error as e:
        logger.debug("cursor session name: could not open %s: %s", db_path, e)
        return ""
    try:
        tables = ("cursorDiskKV", "ItemTable")
        for cid in candidates:
            for table in tables:
                for key in (f"composerData:{cid}", f"composerData:{cid.lower()}"):
                    raw = _read_kv_value(conn, table, key)
                    if not raw:
                        continue
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    name = _name_from_composer_json(data, conversation_id)
                    if name:
                        return name

        # Intentionally no broad ``value LIKE`` scan: Cursor's global DB can be
        # very large and unindexed substring scans would stall the daemon.
    except Exception as e:
        logger.debug("cursor session name read failed: %s", e)
        return ""
    finally:
        conn.close()
    return ""


class _TurnState:
    """Open-span state for one turn (generation_id) within a conversation."""

    def __init__(self) -> None:
        self.agent_span: Span | None = None
        self.agent_ctx: Any = None
        self.prompt: str = ""
        self.response: str = ""
        self.transcript_path: str = ""
        self.attachments: list[dict] = []
        # Unix timestamp when the user prompt was received — used to find
        # screenshots that Cursor saves to disk AFTER the hook fires.
        self._prompt_timestamp: float = 0.0
        # Populated by the background upload thread; read in _close_turn.
        self._content_refs: list[dict] = []
        self._upload_thread: threading.Thread | None = None
        # tool_use_id → (Span, ctx)
        self.tool_spans: dict[str, tuple[Span, Any]] = {}
        # subagent_id → Span
        self.subagent_spans: dict[str, Span] = {}


class _ConvState:
    """State for one conversation (conversation_id), holding per-turn state."""

    def __init__(self) -> None:
        self.model: str = ""
        self.source: str = ""
        self.workspace: str = ""
        self.is_background_agent: bool = False
        self.composer_mode: str = ""
        self.conversation_name: str = ""
        self.current_turn: _TurnState | None = None


class SpanBuilder:
    """Manages the OTel span lifecycle for all active agent conversations.

    Each turn (identified by ``generation_id``) gets its own root
    ``invoke_agent`` span.  Turns within a conversation share
    ``gen_ai.conversation.id``.

    Args:
        provider: Configured OTel ``TracerProvider``.  Must have exporters
            set up before the first event is processed.

    Examples:
        >>> from opentelemetry.sdk.trace import TracerProvider
        >>> builder = SpanBuilder(TracerProvider())
        >>> # events come in via builder.handle(event)
    """

    def __init__(
        self,
        provider: TracerProvider,
        project_id: str = "",
        server_url: str = "",
        api_key: str = "",
    ) -> None:
        self._provider = provider
        self._tracer = provider.get_tracer("weave.agent_hooks")
        self._lock = threading.Lock()
        self._convs: dict[str, _ConvState] = {}
        self._project_id = project_id
        self._server_url = server_url
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def handle(self, event: AgentHookEvent) -> None:
        """Dispatch a normalized event to the appropriate handler."""
        try:
            self._dispatch(event)
        except Exception:
            logger.exception("span_builder error on %s", event.event_kind)

    def flush(self) -> None:
        """Force-flush all pending spans to the exporter."""
        self._provider.force_flush()

    def shutdown(self) -> None:
        """Flush and shut down the provider."""
        self._provider.force_flush()
        self._provider.shutdown()

    # ------------------------------------------------------------------
    # Internal dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, ev: AgentHookEvent) -> None:
        logger.info(
            "event %-20s conv=%.16s gen=%.8s tool=%s",
            ev.event_kind,
            ev.conversation_id or "-",
            ev.generation_id or "-",
            ev.tool_name or "-",
        )
        kind = ev.event_kind
        if kind == "session_start":
            self._on_session_start(ev)
        elif kind == "session_end":
            self._on_session_end(ev)
        elif kind == "user_prompt":
            self._on_user_prompt(ev)
        elif kind == "agent_response":
            self._on_agent_response(ev)
        elif kind == "agent_thought":
            self._on_agent_thought(ev)
        elif kind == "tool_use_start":
            self._on_tool_use_start(ev)
        elif kind in {"tool_use_end", "tool_use_failed"}:
            self._on_tool_use_end(ev)
        elif kind == "shell_exec":
            self._on_shell_exec(ev)
        elif kind == "mcp_call":
            self._on_mcp_call(ev)
        elif kind == "file_edit":
            self._on_file_edit(ev)
        elif kind == "subagent_start":
            self._on_subagent_start(ev)
        elif kind == "subagent_stop":
            self._on_subagent_stop(ev)
        elif kind == "context_compacted":
            self._on_context_compacted(ev)
        elif kind == "post_compact":
            self._on_post_compact(ev)
        elif kind == "stop":
            self._on_stop(ev)
        elif kind == "stop_failure":
            self._on_stop_failure(ev)

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _get_conv(self, conv_id: str) -> _ConvState:
        with self._lock:
            if conv_id not in self._convs:
                self._convs[conv_id] = _ConvState()
            return self._convs[conv_id]

    def _get_turn(self, ev: AgentHookEvent) -> tuple[_ConvState, _TurnState | None]:
        """Return (conv, turn) where turn may be ``None`` if no turn is open.

        Only ``_on_user_prompt`` opens turns.  All other handlers should call
        this and skip gracefully when turn is ``None`` — those events arrived
        outside a user-initiated turn boundary (e.g. after a daemon restart
        or between ``stop`` and the next ``beforeSubmitPrompt``).
        """
        conv = self._get_conv(ev.conversation_id)
        if conv.source == "" and ev.source:
            conv.source = ev.source
        if conv.model == "" and ev.model:
            conv.model = ev.model
        if conv.workspace == "" and ev.workspace_roots:
            conv.workspace = ev.workspace_roots[0]
        return conv, conv.current_turn

    def _open_turn(self, conv: _ConvState, ev: AgentHookEvent) -> _TurnState:
        """Open a new turn: create root invoke_agent span."""
        agent_label = f"{conv.source or ev.source or 'ide'}-agent"
        workspace = conv.workspace or (ev.workspace_roots[0] if ev.workspace_roots else "")

        turn = _TurnState()
        model = ev.model or conv.model
        llm_provider = _provider_from_model(model) or conv.source or ev.source or "ide"
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": agent_label,
            "gen_ai.system": llm_provider,
            "gen_ai.request.model": model,
            "gen_ai.conversation.id": ev.conversation_id,
            "gen_ai.conversation.name": conv.conversation_name,
            "weave.agent_hooks.source": conv.source or ev.source or "ide",
            "weave.agent_hooks.workspace": workspace,
        }
        if conv.composer_mode:
            attrs["weave.session.composer_mode"] = conv.composer_mode
        if conv.is_background_agent:
            attrs["weave.session.is_background_agent"] = True

        span, ctx = self._start_span(f"invoke_agent {agent_label}", None, attrs)
        turn.agent_span = span
        turn.agent_ctx = ctx
        conv.current_turn = turn
        return turn

    def _close_turn(self, conv: _ConvState, stop_status: str = "", loop_count: int = 0) -> None:
        """Close the current turn: attach prompt/response to root span, end all spans."""
        turn = conv.current_turn
        if turn is None:
            return

        # Wait for any in-progress explicit attachment uploads.
        if turn._upload_thread is not None:
            turn._upload_thread.join(timeout=30)

        # Scan for screenshots Cursor saved after the hook fired and upload them.
        screenshot_refs = self._collect_cursor_screenshots(turn)
        if screenshot_refs:
            turn._content_refs = turn._content_refs + screenshot_refs

        # Attach user prompt (and any file attachments) to the root invoke_agent span
        if turn.prompt or turn.attachments:
            input_msgs = []
            if turn.attachments:
                # Represent attached files/rules as context in the message array
                attachment_paths = [
                    a.get("file_path", "") for a in turn.attachments if a.get("file_path")
                ]
                if attachment_paths:
                    turn.agent_span.set_attribute(  # type: ignore[union-attr]
                        "weave.prompt.attachments", json.dumps(attachment_paths)
                    )
            if turn.prompt:
                input_msgs.append({"role": "user", "content": turn.prompt})
            if input_msgs:
                turn.agent_span.set_attribute(  # type: ignore[union-attr]
                    "gen_ai.input.messages", json.dumps(input_msgs)
                )

        # Attach final assistant response to the root span (e.g. from
        # Claude Code's Stop.last_assistant_message or Cursor agent_response).
        if turn.response:
            turn.agent_span.set_attribute(  # type: ignore[union-attr]
                "gen_ai.output.messages",
                json.dumps([{"role": "assistant", "content": turn.response}]),
            )

        # Attach content refs for uploaded attachments (images, files, etc.)
        if turn._content_refs:
            turn.agent_span.set_attribute(  # type: ignore[union-attr]
                _CONTENT_REFS_ATTR, json.dumps(turn._content_refs)
            )

        # Record turn completion metadata
        if stop_status:
            turn.agent_span.set_attribute(  # type: ignore[union-attr]
                "weave.turn.stop_status", stop_status
            )
        if loop_count:
            turn.agent_span.set_attribute(  # type: ignore[union-attr]
                "weave.turn.loop_count", loop_count
            )

        # Store the transcript path so viewers can open the raw file
        if turn.transcript_path:
            turn.agent_span.set_attribute(  # type: ignore[union-attr]
                "weave.turn.transcript_path", turn.transcript_path
            )
            # Opportunistically read and attach the transcript content
            content = _read_transcript(turn.transcript_path)
            if content:
                turn.agent_span.set_attribute(  # type: ignore[union-attr]
                    "weave.turn.transcript", content[:_TRANSCRIPT_TRUNCATE]
                )

        # Set OTel span status based on stop outcome
        if stop_status == "error":
            from opentelemetry.trace import StatusCode
            turn.agent_span.set_status(StatusCode.ERROR, "agent error")  # type: ignore[union-attr]
        elif stop_status == "aborted":
            turn.agent_span.set_attribute(  # type: ignore[union-attr]
                "weave.turn.aborted", True
            )

        # Close any dangling child spans
        for tool_span, _ in turn.tool_spans.values():
            tool_span.end()
        turn.tool_spans.clear()

        for sub_span in turn.subagent_spans.values():
            sub_span.end()
        turn.subagent_spans.clear()

        if turn.agent_span:
            turn.agent_span.end()

        conv.current_turn = None

    def _start_span(
        self,
        name: str,
        parent_ctx: Any,
        attributes: dict[str, Any],
    ) -> tuple[Span, Any]:
        """Start a span with *parent_ctx* and return (span, ctx_with_span)."""
        from opentelemetry import trace

        span = self._tracer.start_span(name, context=parent_ctx, attributes=attributes)
        ctx = trace.set_span_in_context(span)
        return span, ctx

    # ------------------------------------------------------------------
    # Attachment upload helpers
    # ------------------------------------------------------------------

    def _upload_attachment(self, attachment: dict) -> dict | None:
        """Upload a single attachment file to the Weave file store.

        Reads the file at ``attachment["file_path"]``, detects its MIME type,
        uploads it via ``POST {server_url}/file/create``, and returns a
        content-ref dict compatible with ``weave.content_refs``.

        Args:
            attachment: A dict from ``beforeSubmitPrompt.attachments``, expected
                to have a ``"file_path"`` key with an absolute path.

        Returns:
            A content-ref dict, or ``None`` if the upload cannot be performed
            (missing config, missing file, or network error).
        """
        if not self._project_id or not self._server_url:
            return None

        file_path = attachment.get("file_path", "")
        if not file_path:
            return None

        p = Path(file_path)
        if not p.is_file():
            logger.debug("Attachment not found on disk: %s", file_path)
            return None

        try:
            content = p.read_bytes()
        except OSError:
            logger.debug("Could not read attachment: %s", file_path, exc_info=True)
            return None

        try:
            from weave.otel._storage import detect_media_type
            media_type = detect_media_type(content, p.name)
        except Exception:
            media_type = "application/octet-stream"

        try:
            from weave.shared.digest import bytes_digest
            digest = bytes_digest(content)
        except Exception:
            import hashlib
            digest = hashlib.sha256(content).hexdigest()

        url = f"{self._server_url}/file/create"
        headers: dict[str, str] = {}
        if self._api_key:
            creds = base64.b64encode(f"api:{self._api_key}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"

        try:
            import requests
            resp = requests.post(
                url,
                files={"file": (p.name, io.BytesIO(content), "application/octet-stream")},
                data={"project_id": self._project_id},
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
        except Exception:
            logger.debug(
                "Failed to upload attachment %s to %s", file_path, url, exc_info=True
            )

        return {
            "digest": digest,
            "media_type": media_type,
            "role": "input",
            "size_bytes": len(content),
            "key": p.name,
        }

    def _run_attachment_uploads(
        self, turn: _TurnState, attachments: list[dict]
    ) -> None:
        """Upload all attachments and store refs on the turn (runs in a thread).

        Args:
            turn: The turn state to write ``_content_refs`` into.
            attachments: List of attachment dicts from the prompt event.
        """
        refs = []
        for att in attachments:
            ref = self._upload_attachment(att)
            if ref:
                refs.append(ref)
        turn._content_refs = refs

    _SCREENSHOT_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"})

    def _collect_cursor_screenshots(self, turn: _TurnState) -> list[dict]:
        """Find and upload screenshots Cursor saved during this turn.

        Cursor saves screenshot/pasted images to
        ``~/.cursor/projects/<project>/assets/`` *after* the hook fires
        (typically 1–10 seconds later).  We scan that directory at turn-close
        time — well after ``stop`` fires — so all images are guaranteed to be
        on disk.  We only pick up files whose mtime is ≥ the prompt timestamp
        (minus a 2 s grace period) to avoid re-uploading screenshots from
        earlier turns.

        Args:
            turn: The current turn whose prompt timestamp is used as the cutoff.

        Returns:
            List of content-ref dicts for the uploaded screenshots.
        """
        if not self._project_id or not self._server_url:
            return []
        if not turn._prompt_timestamp:
            return []

        # Derive the assets dir from the transcript path.
        # transcript_path: ~/.cursor/projects/<proj>/agent-transcripts/<id>.jsonl
        candidates: list[Path] = []
        if turn.transcript_path:
            p = Path(turn.transcript_path)
            candidates.append(p.parent.parent / "assets")

        # Fallback: scan all Cursor project assets dirs.
        cursor_projects = Path(os.path.expanduser("~/.cursor/projects"))
        if cursor_projects.is_dir():
            try:
                for proj_dir in cursor_projects.iterdir():
                    a = proj_dir / "assets"
                    if a.is_dir():
                        candidates.append(a)
            except OSError:
                pass

        cutoff = turn._prompt_timestamp - 2.0  # 2 s grace period
        seen: set[str] = set()
        refs: list[dict] = []

        for assets_dir in candidates:
            if not assets_dir.is_dir():
                continue
            try:
                for entry in assets_dir.iterdir():
                    path_str = str(entry)
                    if path_str in seen:
                        continue
                    if entry.suffix.lower() not in self._SCREENSHOT_SUFFIXES:
                        continue
                    try:
                        if entry.stat().st_mtime < cutoff:
                            continue
                    except OSError:
                        continue
                    seen.add(path_str)
                    ref = self._upload_attachment({"file_path": path_str})
                    if ref:
                        refs.append(ref)
            except OSError:
                pass

        if refs:
            logger.info("Uploaded %d screenshot(s) for this turn", len(refs))
        return refs

    # ------------------------------------------------------------------
    # Annotation helpers
    # ------------------------------------------------------------------

    def _write_annotation(
        self,
        entity_type: str,
        entity_id: str,
        namespace: str,
        key: str,
        value: str,
        source: str = "hook",
    ) -> None:
        """Write an annotation to the Weave annotations API (fire-and-forget)."""
        if not self._server_url or not self._project_id:
            return
        try:
            url = f"{self._server_url}/genai/annotations/upsert"
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self._api_key:
                headers["wandb-api-key"] = self._api_key
            payload = {
                "project_id": self._project_id,
                "annotations": [{
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "namespace": namespace,
                    "key": key,
                    "string_value": value,
                    "value_type": "string",
                    "source": source,
                }],
            }
            requests.post(url, json=payload, headers=headers, timeout=5)
        except Exception:
            logger.debug("Failed to write annotation", exc_info=True)

    def _maybe_sync_cursor_conversation_title(self, ev: AgentHookEvent) -> None:
        """Update ``conversation_name`` from Cursor's local DB when available.

        Cursor often persists the sidebar title only after the model responds,
        so this must run on ``afterAgentResponse`` / ``stop`` as well as
        ``beforeSubmitPrompt``.
        """
        if ev.source != "cursor" or not ev.conversation_id:
            return
        raw = ev.raw or {}
        extra = tuple(
            str(raw[k])
            for k in ("composer_id", "composerId", "chatId", "composerSessionId")
            if raw.get(k)
        )
        title = _read_cursor_session_name(
            ev.conversation_id,
            transcript_path=ev.transcript_path or "",
            extra_ids=extra,
        )
        if not title:
            return
        conv = self._get_conv(ev.conversation_id)
        if title == conv.conversation_name:
            return
        conv.conversation_name = title
        self._write_annotation(
            "conversation",
            ev.conversation_id,
            "display",
            "name",
            conv.conversation_name,
        )
        # Keep the open root span aligned so OTLP exports don't reintroduce
        # empty names that break ClickHouse aggregates.
        if conv.current_turn and conv.current_turn.agent_span is not None:
            conv.current_turn.agent_span.set_attribute(
                "gen_ai.conversation.name",
                title,
            )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_session_start(self, ev: AgentHookEvent) -> None:
        conv = self._get_conv(ev.conversation_id)
        conv.source = ev.source
        conv.model = ev.model
        conv.workspace = ev.workspace_roots[0] if ev.workspace_roots else ""
        conv.is_background_agent = ev.is_background_agent
        conv.composer_mode = ev.composer_mode
        if ev.session_id and not _looks_like_uuid(ev.session_id):
            conv.conversation_name = ev.session_id
            self._write_annotation(
                "conversation", ev.conversation_id, "display", "name",
                conv.conversation_name,
            )

    def _on_session_end(self, ev: AgentHookEvent) -> None:
        conv = self._get_conv(ev.conversation_id)
        self._close_turn(conv)
        with self._lock:
            self._convs.pop(ev.conversation_id, None)
        self._provider.force_flush()

    def _on_stop(self, ev: AgentHookEvent) -> None:
        """Agent loop ended for one turn — close turn with status, export spans."""
        if ev.source == "cursor":
            self._maybe_sync_cursor_conversation_title(ev)
        conv = self._get_conv(ev.conversation_id)
        # Claude Code provides last_assistant_message on Stop — capture it as
        # the turn response so it appears on the root invoke_agent span.
        if ev.response_text and conv.current_turn:
            conv.current_turn.response = ev.response_text
        self._close_turn(conv, stop_status=ev.stop_status, loop_count=ev.loop_count)

    def _on_user_prompt(self, ev: AgentHookEvent) -> None:
        conv = self._get_conv(ev.conversation_id)
        self._maybe_sync_cursor_conversation_title(ev)
        # Cursor: do not persist truncated prompts as display names — they fight
        # the real sidebar title and cause visible flapping vs annotations.
        if (
            not conv.conversation_name
            and ev.prompt_text
            and ev.source != "cursor"
        ):
            conv.conversation_name = ev.prompt_text[:60]
            self._write_annotation(
                "conversation", ev.conversation_id, "display", "name",
                conv.conversation_name,
            )
        # Close any previous turn that wasn't closed by stop
        self._close_turn(conv)
        # Open a new turn
        turn = self._open_turn(conv, ev)
        turn.prompt = ev.prompt_text
        turn.attachments = ev.attachments
        turn._prompt_timestamp = time.time()
        if ev.transcript_path:
            turn.transcript_path = ev.transcript_path

        # Kick off attachment uploads in the background so they run concurrently
        # with the agent's processing.  Results are collected in _close_turn.
        if ev.attachments and self._project_id and self._server_url:
            t = threading.Thread(
                target=self._run_attachment_uploads,
                args=(turn, ev.attachments),
                daemon=True,
            )
            t.start()
            turn._upload_thread = t

        # Emit an instant child span carrying the user prompt so it is
        # exported immediately, even if the daemon is killed before stop fires.
        # The chat view's find_user_prompt() picks this up as a fallback when
        # the root invoke_agent span is missing.
        if ev.prompt_text:
            attrs: dict[str, Any] = {
                "gen_ai.operation.name": "chat",
                "gen_ai.conversation.id": ev.conversation_id,
                "gen_ai.input.messages": json.dumps(
                    [{"role": "user", "content": ev.prompt_text}]
                ),
            }
            if ev.attachments:
                attachment_paths = [
                    a.get("file_path", "") for a in ev.attachments if a.get("file_path")
                ]
                if attachment_paths:
                    attrs["weave.prompt.attachments"] = json.dumps(attachment_paths)
            user_span, _ = self._start_span("chat", turn.agent_ctx, attrs)
            user_span.end()

    def _on_agent_response(self, ev: AgentHookEvent) -> None:
        if ev.source == "cursor":
            self._maybe_sync_cursor_conversation_title(ev)
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        turn.response = ev.response_text
        if ev.response_text:
            span, _ = self._start_span(
                "chat",
                turn.agent_ctx,
                {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": ev.model or "",
                    "gen_ai.conversation.id": ev.conversation_id,
                    "gen_ai.output.messages": json.dumps(
                        [{"role": "assistant", "content": ev.response_text}]
                    ),
                },
            )
            span.end()

    def _on_agent_thought(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        if ev.thought_text:
            span, _ = self._start_span(
                "chat",
                turn.agent_ctx,
                {
                    "gen_ai.operation.name": "chat",
                    "gen_ai.request.model": ev.model or "",
                    "gen_ai.conversation.id": ev.conversation_id,
                    "gen_ai.output.messages": json.dumps(
                        [{"role": "assistant", "content": ev.thought_text}]
                    ),
                },
            )
            span.end()

    def _on_tool_use_start(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        tool_args = json.dumps(ev.tool_input) if ev.tool_input else ""
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": "execute_tool",
            "gen_ai.tool.name": ev.tool_name,
            "gen_ai.tool.call.arguments": tool_args,
            "gen_ai.conversation.id": ev.conversation_id,
        }
        # Capture the agent's stated reasoning for invoking this tool — this is
        # model output that shows *why* the tool is being called.
        if ev.agent_message:
            attrs["gen_ai.agent.message"] = ev.agent_message
        if ev.cwd:
            attrs["weave.tool.cwd"] = ev.cwd
        span, ctx = self._start_span(f"execute_tool {ev.tool_name}", turn.agent_ctx, attrs)
        key = ev.tool_use_id or ev.tool_name
        turn.tool_spans[key] = (span, ctx)

    def _on_tool_use_end(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        key = ev.tool_use_id or ev.tool_name
        entry = turn.tool_spans.pop(key, None)
        if entry is None:
            self._emit_instant_tool(ev)
            return

        span, _ = entry
        if ev.event_kind == "tool_use_end" and ev.tool_output:
            span.set_attribute(
                "gen_ai.tool.call.result", ev.tool_output[:_TOOL_OUTPUT_TRUNCATE]
            )
        if ev.event_kind == "tool_use_failed":
            if ev.tool_error:
                span.set_attribute("gen_ai.tool.call.result", ev.tool_error)
            if ev.failure_type:
                span.set_attribute("weave.tool.failure_type", ev.failure_type)
            if ev.is_interrupt:
                span.set_attribute("weave.tool.is_interrupt", True)
            from opentelemetry.trace import StatusCode
            span.set_status(StatusCode.ERROR, ev.tool_error or ev.failure_type or "tool failed")
        span.end()

    def _emit_instant_tool(self, ev: AgentHookEvent) -> None:
        """Emit a single-point span for a tool call with no preToolUse."""
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        tool_args = json.dumps(ev.tool_input) if ev.tool_input else ""
        span, _ = self._start_span(
            f"execute_tool {ev.tool_name}",
            turn.agent_ctx,
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": ev.tool_name,
                "gen_ai.tool.call.arguments": tool_args,
                "gen_ai.tool.call.result": ev.tool_output[:_TOOL_OUTPUT_TRUNCATE],
                "gen_ai.conversation.id": ev.conversation_id,
            },
        )
        span.end()

    def _on_shell_exec(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        # Skip when a Shell tool span is already open (preToolUse covers it)
        if turn.tool_spans:
            return
        span, _ = self._start_span(
            "execute_tool bash",
            turn.agent_ctx,
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "bash",
                "gen_ai.tool.call.arguments": json.dumps({"command": ev.shell_command}),
                "gen_ai.tool.call.result": ev.shell_output[:_TOOL_OUTPUT_TRUNCATE],
                "weave.shell.exit_code": ev.shell_exit_code,
                "gen_ai.conversation.id": ev.conversation_id,
            },
        )
        if ev.shell_exit_code != 0:
            from opentelemetry.trace import StatusCode

            span.set_status(StatusCode.ERROR, f"exit {ev.shell_exit_code}")
        span.end()

    def _on_mcp_call(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        tool_label = f"{ev.mcp_server}/{ev.tool_name}" if ev.mcp_server else ev.tool_name
        span, _ = self._start_span(
            f"execute_tool {tool_label}",
            turn.agent_ctx,
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": tool_label,
                "gen_ai.tool.call.arguments": json.dumps(ev.tool_input) if ev.tool_input else "",
                "gen_ai.tool.call.result": ev.tool_output[:_TOOL_OUTPUT_TRUNCATE],
                "weave.mcp.server": ev.mcp_server,
                "gen_ai.conversation.id": ev.conversation_id,
            },
        )
        span.end()

    def _on_file_edit(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        # Skip when a Write tool span is already open (preToolUse covers it)
        if turn.tool_spans:
            return
        span, _ = self._start_span(
            "execute_tool edit_file",
            turn.agent_ctx,
            {
                "gen_ai.operation.name": "execute_tool",
                "gen_ai.tool.name": "edit_file",
                "gen_ai.tool.call.arguments": json.dumps({"path": ev.file_path}),
                "weave.file.path": ev.file_path,
                "weave.file.edit_count": len(ev.file_edits),
                "gen_ai.conversation.id": ev.conversation_id,
            },
        )
        span.end()

    def _on_subagent_start(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        agent_label = ev.subagent_type or "subagent"
        attrs: dict[str, Any] = {
            "gen_ai.operation.name": "invoke_agent",
            "gen_ai.agent.name": agent_label,
            "gen_ai.request.model": ev.subagent_model or ev.model or "",
            "gen_ai.system_instructions": ev.subagent_task,
            "gen_ai.conversation.id": ev.conversation_id,
            "weave.subagent.id": ev.subagent_id,
            "weave.subagent.type": ev.subagent_type,
        }
        if ev.tool_call_id:
            attrs["weave.subagent.tool_call_id"] = ev.tool_call_id
        if ev.is_parallel_worker:
            attrs["weave.subagent.is_parallel_worker"] = True
        if ev.git_branch:
            attrs["weave.subagent.git_branch"] = ev.git_branch
        span, _ = self._start_span(f"invoke_agent {agent_label}", turn.agent_ctx, attrs)
        turn.subagent_spans[ev.subagent_id] = span

    def _on_subagent_stop(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        span = turn.subagent_spans.pop(ev.subagent_id, None)
        if span is None:
            return
        if ev.subagent_summary:
            span.set_attribute("gen_ai.output.messages", json.dumps(
                [{"role": "assistant", "content": ev.subagent_summary}]
            ))
        span.set_attribute("weave.subagent.status", ev.subagent_status)
        span.set_attribute("weave.subagent.tool_call_count", ev.subagent_tool_call_count)
        if ev.subagent_message_count:
            span.set_attribute("weave.subagent.message_count", ev.subagent_message_count)
        if ev.subagent_loop_count:
            span.set_attribute("weave.subagent.loop_count", ev.subagent_loop_count)
        if ev.subagent_modified_files:
            span.set_attribute(
                "weave.subagent.modified_files",
                json.dumps(ev.subagent_modified_files),
            )
        if ev.agent_transcript_path:
            span.set_attribute("weave.subagent.transcript_path", ev.agent_transcript_path)
        if ev.subagent_status == "error":
            from opentelemetry.trace import StatusCode

            span.set_status(StatusCode.ERROR, "subagent failed")
        span.end()

    def _on_context_compacted(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        if turn.agent_span:
            event_attrs: dict[str, Any] = {
                "context_tokens": ev.context_tokens,
                "context_window_size": ev.context_window,
                "usage_pct": round(ev.context_tokens / max(ev.context_window, 1) * 100),
            }
            if ev.compact_trigger:
                event_attrs["trigger"] = ev.compact_trigger
            if ev.context_usage_percent:
                event_attrs["context_usage_percent"] = ev.context_usage_percent
            if ev.message_count:
                event_attrs["message_count"] = ev.message_count
            if ev.messages_to_compact:
                event_attrs["messages_to_compact"] = ev.messages_to_compact
            # Always record is_first_compaction (False is informative too)
            event_attrs["is_first_compaction"] = ev.is_first_compaction
            turn.agent_span.add_event("context_compacted", event_attrs)

    def _on_post_compact(self, ev: AgentHookEvent) -> None:
        _, turn = self._get_turn(ev)
        if turn is None:
            return
        if turn.agent_span and ev.compact_summary:
            turn.agent_span.add_event(
                "post_compact",
                {
                    "trigger": ev.compact_trigger,
                    "summary_length": len(ev.compact_summary),
                },
            )

    def _on_stop_failure(self, ev: AgentHookEvent) -> None:
        """Turn ended due to an API error — close with error status."""
        conv = self._get_conv(ev.conversation_id)
        if conv.current_turn and conv.current_turn.agent_span:
            span = conv.current_turn.agent_span
            if ev.stop_error:
                span.set_attribute("weave.turn.stop_error", ev.stop_error)
            if ev.stop_error_details:
                span.set_attribute("weave.turn.stop_error_details", ev.stop_error_details)
            from opentelemetry.trace import StatusCode

            span.set_status(StatusCode.ERROR, ev.stop_error or "api_error")
        self._close_turn(conv, stop_status="error")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_transcript(path: str) -> str | None:
    """Read a Cursor transcript file, returning its text content or None.

    Args:
        path: Absolute path to the transcript file.

    Returns:
        File contents as a string, or ``None`` if the file cannot be read.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None
