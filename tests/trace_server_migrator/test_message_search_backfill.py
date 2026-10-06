import json
import uuid
from datetime import datetime, timezone

import pytest

from weave.trace_server.clickhouse_trace_server_migrator import (
    get_clickhouse_trace_server_migrator,
)
from weave.trace_server.message_search_backfill import MessageSearchBackfill


def test_backfill_resume_verify_and_retention(ch_client, tmp_path, monkeypatch):
    database = f"backfill_{uuid.uuid4().hex[:8]}"
    ch_client.track_db(database + "_management")
    ch_client.track_db(database)
    migrator = get_clickhouse_trace_server_migrator(
        ch_client,
        management_db=database + "_management",
        post_migration_hook=None,
    )
    migrator.apply_migrations(database, target_version=47)
    previous_db = ch_client.database
    ch_client.database = database
    try:
        ch_client.command("""INSERT INTO messages (project_id, content_digest, content, span_id,
            started_at, created_at, expire_at)
            SELECT 'p', murmurHash3_128('hello'), 'hello', 'old',
            toDateTime64('2025-01-01', 6), toDateTime64('2025-01-02', 3), toDateTime('2090-01-01')""")
        migrator.apply_migrations(database, target_version=48)
        # Live capture must also catch late-arriving event times.
        ch_client.command("""INSERT INTO messages (project_id, content_digest, content, span_id,
            started_at, expire_at)
            SELECT 'p', murmurHash3_128('hello'), 'hello', 'live',
            toDateTime64('2024-01-01', 6), toDateTime('2099-01-01')""")
        checkpoint = tmp_path / "backfill.json"
        job = MessageSearchBackfill(ch_client, checkpoint)
        cutoff = datetime(2025, 2, 1, tzinfo=timezone.utc)
        command = ch_client.command

        def interrupt(cmd, *args, **kwargs):
            if cmd.startswith("INSERT INTO message_occurrences"):
                raise RuntimeError("interrupted between tables")
            return command(cmd, *args, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(ch_client, "command", interrupt)
            with pytest.raises(RuntimeError, match="interrupted between tables"):
                job.run(before=cutoff)
        assert json.loads(checkpoint.read_text())["windows"] == []
        result = job.run(before=cutoff)
        assert result["cursor"] == result["end"]
        job.run(validate_only=True)
        assert job.run() == result
        assert ch_client.query(
            "SELECT span_id FROM message_occurrences FINAL ORDER BY span_id"
        ).result_rows == [("live",), ("old",)]
        assert ch_client.query(
            "SELECT content, toYear(expire_at) FROM message_content FINAL"
        ).result_rows == [("hello", 2099)]
        ch_client.command(
            "ALTER TABLE message_occurrences DELETE WHERE span_id = 'old' SETTINGS mutations_sync = 2"
        )
        with pytest.raises(ValueError, match="1 occurrences missing or inconsistent"):
            job.run(validate_only=True)
        MessageSearchBackfill(ch_client, tmp_path / "repair.json").run(before=cutoff)
        job.run(validate_only=True)
        with pytest.raises(ValueError, match="another database, schema, or project"):
            MessageSearchBackfill(ch_client, checkpoint, project_id="other").run()
    finally:
        ch_client.database = previous_db
