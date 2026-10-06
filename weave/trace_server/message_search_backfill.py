"""Resumable message search backfill. See agents/message-search.md for rollout."""

import argparse
import fcntl
import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.client import Client
from clickhouse_connect.driver.summary import QuerySummary

from weave.trace_server import environment as env

OCCURRENCE_COLUMNS = (
    "project_id, content_digest, trace_id, span_id, parent_span_id, "
    "conversation_id, conversation_name, agent_name, agent_version, "
    "provider_name, request_model, operation_name, role, started_at, "
    "wb_user_id, created_at, expire_at"
)
KEY = "project_id, started_at, span_id, trace_id, role, content_digest"
METADATA = (
    "parent_span_id, conversation_id, conversation_name, agent_name, agent_version, "
    "provider_name, request_model, operation_name, wb_user_id, expire_at"
)


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamps must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _server_utc(value: datetime) -> datetime:
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


class MessageSearchBackfill:
    def __init__(
        self,
        client: Client,
        checkpoint: Path,
        *,
        project_id: str | None = None,
        window_hours: int = 1,
        local_tables: bool = False,
        max_threads: int = 2,
        max_memory_usage: int = 4 * 1024**3,
    ) -> None:
        if window_hours <= 0 or max_threads <= 0 or max_memory_usage <= 0:
            raise ValueError("Window and resource limits must be positive")
        self.client = client
        self.checkpoint = checkpoint
        self.project_id = project_id
        self.window = timedelta(hours=window_hours)
        self.suffix = "_local" if local_tables else ""
        self.settings = {
            "max_threads": max_threads,
            "max_memory_usage": max_memory_usage,
            "max_execution_time": 3600,
            "insert_deduplicate": 0,
            "async_insert": 0,
        }

    def _identity(self) -> str:
        rows = self.client.query(
            "SELECT name, toString(uuid), engine FROM system.tables "
            "WHERE database = currentDatabase() AND name IN {names:Array(String)} "
            "ORDER BY name",
            parameters={
                "names": [
                    f"{name}{self.suffix}"
                    for name in (
                        "messages",
                        "message_content",
                        "message_occurrences",
                        "message_content_mv",
                        "message_occurrences_mv",
                    )
                ]
            },
        ).result_rows
        if len(rows) != 5:
            raise ValueError("Apply migration 048, including both capture MVs, first")
        if any(row[2] == "Distributed" for row in rows):
            raise ValueError(
                "Run once per shard with --local-tables on distributed deployments"
            )
        return hashlib.sha256(
            json.dumps([self.client.database, rows, self.project_id]).encode()
        ).hexdigest()

    def _save(self, state: dict[str, Any]) -> None:
        temporary = self.checkpoint.with_suffix(".tmp")
        self.checkpoint.parent.mkdir(parents=True, exist_ok=True)
        with temporary.open("w") as out:
            json.dump(state, out, indent=2)
            out.flush()
            os.fsync(out.fileno())
        temporary.replace(self.checkpoint)

    def initialize(self, *, before: datetime | None = None) -> dict[str, Any]:
        identity = self._identity()
        if self.checkpoint.exists():
            state = json.loads(self.checkpoint.read_text())
            if state["identity"] != identity:
                raise ValueError(
                    "Checkpoint belongs to another database, schema, or project"
                )
            if before is not None and state["before"] != before.isoformat():
                raise ValueError("Cannot change the cutoff of an existing checkpoint")
            return state
        server_now = _server_utc(
            self.client.query("SELECT now64(3, 'UTC')").first_row[0]
        )
        before = before or server_now
        if before > server_now:
            raise ValueError("Cutoff cannot be in the future")
        params: dict[str, Any] = {"before": before}
        condition = "created_at < {before:DateTime64(3)}"
        if self.project_id is not None:
            params["project"] = self.project_id
            condition += " AND project_id = {project:String}"
        count, start, end = self.client.query(
            f"SELECT count(), min(toTimeZone(started_at, 'UTC')), max(toTimeZone(started_at, 'UTC')) "
            f"FROM messages{self.suffix} WHERE {condition}",
            parameters=params,
        ).first_row
        start, end = _server_utc(start), _server_utc(end)
        state = {
            "identity": identity,
            "before": before.isoformat(),
            "start": start.isoformat() if count else before.isoformat(),
            "end": (end + timedelta(microseconds=1)).isoformat()
            if count
            else before.isoformat(),
            "cursor": start.isoformat() if count else before.isoformat(),
            "windows": [],
        }
        self._save(state)
        return state

    def _scope(
        self, start: datetime, end: datetime, before: datetime
    ) -> tuple[str, dict[str, Any]]:
        params: dict[str, Any] = {"start": start, "end": end, "before": before}
        condition = (
            "started_at >= {start:DateTime64(6)} AND started_at < {end:DateTime64(6)} "
            "AND created_at < {before:DateTime64(3)} AND expire_at > now()"
        )
        if self.project_id is not None:
            params["project"] = self.project_id
            condition += " AND project_id = {project:String}"
        return condition, params

    def validate_window(self, start: datetime, end: datetime, before: datetime) -> None:
        condition, params = self._scope(start, end, before)
        source = f"messages{self.suffix}"
        content = f"message_content{self.suffix}"
        occurrences = f"message_occurrences{self.suffix}"
        missing_content = self.client.query(
            "SELECT count() FROM (SELECT project_id, content_digest, SHA256(content) AS body_hash, "
            f"max(expire_at) AS expiry FROM {source} WHERE {condition} "
            "GROUP BY project_id, content_digest, body_hash) AS s "
            "LEFT JOIN (SELECT project_id, content_digest, SHA256(content) AS body_hash, "
            f"max(expire_at) AS expiry, 1 AS present FROM {content} "
            "WHERE (project_id, content_digest) IN "
            f"(SELECT project_id, content_digest FROM {source} WHERE {condition}) "
            "GROUP BY project_id, content_digest, body_hash) AS d "
            "USING (project_id, content_digest, body_hash) "
            "WHERE d.present = 0 OR d.expiry < s.expiry",
            parameters=params,
            settings=self.settings,
        ).first_row[0]
        # A newer live export may legitimately supersede a historical row.
        missing_occurrences = self.client.query(
            f"SELECT count() FROM (SELECT {KEY}, max(created_at) AS version, "
            f"argMax(tuple({METADATA}), created_at) AS metadata FROM {source} "
            f"WHERE {condition} GROUP BY {KEY}) AS s "
            f"LEFT JOIN (SELECT {KEY}, created_at AS version, tuple({METADATA}) AS metadata, "
            f"1 AS present FROM {occurrences} FINAL "
            "WHERE started_at >= {start:DateTime64(6)} AND started_at < {end:DateTime64(6)}) AS d "
            f"USING ({KEY}) WHERE d.present = 0 OR d.version < s.version "
            "OR (d.version = s.version AND d.metadata != s.metadata)",
            parameters=params,
            settings=self.settings,
        ).first_row[0]
        if missing_content or missing_occurrences:
            raise ValueError(
                f"Backfill validation failed: {missing_content} content rows, "
                f"{missing_occurrences} occurrences missing or inconsistent"
            )

    def run(
        self, *, before: datetime | None = None, validate_only: bool = False
    ) -> dict[str, Any]:
        state = self.initialize(before=before)
        start = _utc(state["start"] if validate_only else state["cursor"])
        end = _utc(state["end"])
        cutoff = _utc(state["before"])
        while start < end:
            stop = min(start + self.window, end)
            began = time.monotonic()
            query_ids = []
            if not validate_only:
                condition, params = self._scope(start, stop, cutoff)
                selects = (
                    (
                        "message_content",
                        "project_id, content_digest, content, expire_at",
                        "project_id, content_digest, content, max(expire_at)",
                        " GROUP BY project_id, content_digest, content",
                    ),
                    ("message_occurrences", OCCURRENCE_COLUMNS, OCCURRENCE_COLUMNS, ""),
                )
                for table, columns, projection, group in selects:
                    result = self.client.command(
                        f"INSERT INTO {table}{self.suffix} ({columns}) SELECT {projection} "
                        f"FROM messages{self.suffix} WHERE {condition}{group}",
                        parameters=params,
                        settings=self.settings,
                    )
                    if isinstance(result, QuerySummary):
                        query_ids.append(result.query_id())
            self.validate_window(start, stop, cutoff)
            record = {
                "start": start.isoformat(),
                "end": stop.isoformat(),
                "elapsed_seconds": round(time.monotonic() - began, 3),
                "query_ids": query_ids,
            }
            if not validate_only:
                state["cursor"] = stop.isoformat()
                state["windows"].append(record)
                self._save(state)
            print(json.dumps(record), flush=True)
            start = stop
        return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--project-id")
    parser.add_argument("--before", type=_utc)
    parser.add_argument("--window-hours", type=int, default=1)
    parser.add_argument("--max-threads", type=int, default=2)
    parser.add_argument("--max-memory-usage", type=int, default=4 * 1024**3)
    parser.add_argument("--local-tables", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    args.checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with (
        args.checkpoint.with_suffix(".lock").open("w") as lock,
        clickhouse_connect.get_client(
            host=env.wf_clickhouse_host(),
            port=env.wf_clickhouse_port(),
            username=env.wf_clickhouse_user(),
            password=env.wf_clickhouse_pass(),
            database=env.wf_clickhouse_database(),
            secure=env.wf_clickhouse_port() == 8443,
        ) as client,
    ):
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        MessageSearchBackfill(
            client,
            args.checkpoint,
            project_id=args.project_id,
            window_hours=args.window_hours,
            local_tables=args.local_tables,
            max_threads=args.max_threads,
            max_memory_usage=args.max_memory_usage,
        ).run(before=args.before, validate_only=args.validate_only)


if __name__ == "__main__":
    main()
