from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time

import pytest

from weave.durability.wal import WALRecord
from weave.durability.wal_consumer import JSONLWALConsumer
from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.durability.wal_lock import is_writer_alive
from weave.durability.wal_sender import BackgroundWALSender
from weave.durability.wal_writer import JSONLWALWriter

# Number of records written by the writer subprocess in cross-process tests.
_SUBPROCESS_RECORD_COUNT = 5


class TestDrainOnce:
    """Tests for BackgroundWALSender.drain_once() without the background thread."""

    def test_delivers_records_to_handler(self, tmp_path: str) -> None:
        """drain_once() reads pending records and dispatches to handlers."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "call_start", "id": "c1"})
            writer.write({"type": "call_end", "id": "c1"})

        received: list[WALRecord] = []
        handlers = {"call_start": received.append, "call_end": received.append}
        sender = BackgroundWALSender(mgr, handlers, JSONLWALConsumer)
        count = sender.drain_once()

        assert count == 2
        assert received[0] == {"type": "call_start", "id": "c1"}
        assert received[1] == {"type": "call_end", "id": "c1"}

    def test_deletes_closed_writer_file_but_keeps_open_writer_file(
        self, tmp_path: str
    ) -> None:
        """Closed files are removed; files with a live writer are kept."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        # First file: writer closed → lock removed → deletable.
        with mgr.create_file() as w1:
            w1.write({"type": "obj_create", "seq": 0})
        # Second file: writer still open → lock has our PID → protected.
        w2 = mgr.create_file()
        w2_path = w2.path
        w2.write({"type": "obj_create", "seq": 1})
        w2.flush()

        assert len(mgr.list_files()) == 2

        received: list[WALRecord] = []
        sender = BackgroundWALSender(
            mgr, {"obj_create": received.append}, JSONLWALConsumer
        )
        sender.drain_once()

        # First file removed; second file kept (writer alive).
        assert mgr.list_files() == [w2_path]
        assert len(received) == 2

        # Writer closes between drain cycles → lock removed.
        # Next drain should clean up the now-inactive file.
        w2.close()
        sender.drain_once()
        assert mgr.list_files() == []

    def test_empty_directory_is_noop(self, tmp_path: str) -> None:
        """No WAL files means drain_once returns 0 without errors."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        sender = BackgroundWALSender(mgr, {}, JSONLWALConsumer)
        assert sender.drain_once() == 0

    def test_multiple_drain_cycles(self, tmp_path: str) -> None:
        """Records written between drain cycles are picked up."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = mgr.create_file()

        received: list[WALRecord] = []
        sender = BackgroundWALSender(
            mgr, {"obj_create": received.append}, JSONLWALConsumer
        )

        writer.write({"type": "obj_create", "seq": 0})
        writer.flush()
        sender.drain_once()
        assert len(received) == 1

        writer.write({"type": "obj_create", "seq": 1})
        writer.flush()
        sender.drain_once()
        assert len(received) == 2

        assert [r["seq"] for r in received] == [0, 1]
        writer.close()

    def test_drains_multiple_files_from_previous_run(self, tmp_path: str) -> None:
        """Files left by a previous process that shut down cleanly (lock removed)
        but whose records were never drained are picked up and cleaned up.
        """
        mgr = FileWALDirectoryManager(str(tmp_path))

        # Two files from a previous run — writers closed, no lock files.
        with mgr.create_file() as w1:
            w1.write({"type": "call_start", "id": "orphan-1"})
        with mgr.create_file() as w2:
            w2.write({"type": "call_start", "id": "orphan-2"})
            w2.write({"type": "call_end", "id": "orphan-2"})

        received: list[WALRecord] = []
        handlers = {"call_start": received.append, "call_end": received.append}
        sender = BackgroundWALSender(mgr, handlers, JSONLWALConsumer)
        sender.drain_once()

        assert len(received) == 3
        assert mgr.list_files() == []

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Windows locks open files — can't unlink while consumer holds a handle",
    )
    def test_consumer_evicted_when_file_removed_externally(self, tmp_path: str) -> None:
        """If a file disappears between drain cycles, its cached consumer
        is evicted without error.
        """
        mgr = FileWALDirectoryManager(str(tmp_path))

        # Create a file that stays open (writer alive → sender caches
        # a consumer but won't delete the file).
        writer = mgr.create_file()
        writer.write({"type": "obj_create", "seq": 0})
        writer.flush()
        wal_path = writer.path

        received: list[WALRecord] = []
        sender = BackgroundWALSender(
            mgr, {"obj_create": received.append}, JSONLWALConsumer
        )

        # First drain — caches a consumer for the file.
        sender.drain_once()
        assert len(received) == 1
        assert len(mgr.list_files()) == 1  # kept because writer is alive

        # Close the writer (releases the lock) then externally unlink the
        # file.  On Unix, unlink succeeds even though the sender's cached
        # consumer still has an open fd.
        writer.close()
        os.unlink(wal_path)

        # Next drain: list_files() returns nothing, so the cached consumer
        # for the now-missing file must be evicted without error.
        sender.drain_once()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Background thread timing is unreliable on Windows CI runners",
)
class TestBackgroundThread:
    """Tests for the background drain thread."""

    def test_start_and_stop(self, tmp_path: str) -> None:
        """Sender starts a thread and stops cleanly."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        sender = BackgroundWALSender(mgr, {}, JSONLWALConsumer, poll_interval=0.05)

        sender.start()
        assert sender._thread is not None
        assert sender._thread.is_alive()

        sender.stop()
        assert sender._thread is None

    def test_start_twice_raises(self, tmp_path: str) -> None:
        """Starting the sender twice raises RuntimeError."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        sender = BackgroundWALSender(mgr, {}, JSONLWALConsumer, poll_interval=0.05)

        sender.start()
        try:
            with pytest.raises(RuntimeError, match="already running"):
                sender.start()
        finally:
            sender.stop()

    def test_background_drains_records(self, tmp_path: str) -> None:
        """Background thread picks up records automatically."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = mgr.create_file()

        got_record = threading.Event()
        received: list[WALRecord] = []

        def handler(record: WALRecord) -> None:
            received.append(record)
            got_record.set()

        sender = BackgroundWALSender(
            mgr,
            {"obj_create": handler},
            JSONLWALConsumer,
            poll_interval=0.05,
        )
        sender.start()

        try:
            writer.write({"type": "obj_create", "seq": 0})
            writer.flush()

            assert got_record.wait(timeout=2.0), "background thread did not drain"
            assert len(received) == 1
            assert received[0]["seq"] == 0
        finally:
            writer.close()
            sender.stop()

    def test_stop_does_final_drain(self, tmp_path: str) -> None:
        """stop() performs a final drain of remaining records."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = JSONLWALWriter(mgr)

        received: list[WALRecord] = []
        sender = BackgroundWALSender(
            mgr,
            {"obj_create": received.append},
            JSONLWALConsumer,
            poll_interval=60.0,
        )
        # Long poll interval ensures the background thread won't drain
        # during the window between write and stop.
        sender.start()

        writer.write({"type": "obj_create", "seq": 0})

        # Close writer first → lock file removed → file deletable.
        writer.close()
        sender.stop()

        assert len(received) == 1
        assert received[0]["seq"] == 0
        assert mgr.list_files() == []


class TestErrorResilience:
    """Tests for error handling in the sender."""

    @pytest.mark.disable_logging_error_check
    def test_handler_error_doesnt_block_other_records(self, tmp_path: str) -> None:
        """Handler errors don't stop the sender from processing other records."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})
            writer.write({"type": "obj_create", "seq": 1})
            writer.write({"type": "obj_create", "seq": 2})

        results: list[int] = []

        def handler(record: WALRecord) -> None:
            if record["seq"] == 1:
                raise ValueError("boom")
            results.append(record["seq"])

        sender = BackgroundWALSender(mgr, {"obj_create": handler}, JSONLWALConsumer)
        count = sender.drain_once()

        # Records 0 and 2 succeeded, record 1 went to dead-letter.
        assert count == 2
        assert results == [0, 2]

    @pytest.mark.disable_logging_error_check
    def test_dead_letter_captures_failed_records(self, tmp_path: str) -> None:
        """Failed records are written to the dead-letter sidecar."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})
            writer.write({"type": "obj_create", "seq": 1})

        def handler(record: WALRecord) -> None:
            if record["seq"] == 1:
                raise RuntimeError("network error")

        path = mgr.list_files()[0]
        # Use a custom is_file_active to protect the file so drain doesn't
        # remove it (and its dead-letter sidecar) before we can inspect it.
        sender = BackgroundWALSender(
            mgr,
            {"obj_create": handler},
            JSONLWALConsumer,
            is_file_active=lambda p: True,
        )
        sender.drain_once()

        # Check the dead-letter file for the failed record.
        base = path.rsplit(".", 1)[0]
        dead_letter_path = base + ".deadletter"
        with open(dead_letter_path, encoding="utf-8") as f:
            dead = [json.loads(line) for line in f]
        assert len(dead) == 1
        assert dead[0]["seq"] == 1

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Background thread timing is unreliable on Windows CI runners",
    )
    @pytest.mark.disable_logging_error_check
    def test_background_thread_survives_handler_error(self, tmp_path: str) -> None:
        """The background thread keeps running after a handler error."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        call_count = 0
        received: list[WALRecord] = []

        def handler(record: WALRecord) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("transient error")
            received.append(record)

        sender = BackgroundWALSender(
            mgr, {"obj_create": handler}, JSONLWALConsumer, poll_interval=0.05
        )
        sender.start()

        try:
            # First record triggers error (goes to dead-letter via drain).
            with mgr.create_file() as w1:
                w1.write({"type": "obj_create", "seq": 0})

            # Wait for background drain to process.
            time.sleep(0.2)

            # Second record should succeed — thread survived the error.
            with mgr.create_file() as w2:
                w2.write({"type": "obj_create", "seq": 1})

            deadline = time.monotonic() + 2.0
            while len(received) < 1 and time.monotonic() < deadline:
                time.sleep(0.02)

            assert len(received) >= 1
            assert received[0]["seq"] == 1
        finally:
            sender.stop()


class TestWithRotatingWriter:
    """Tests combining BackgroundWALSender with the rotating JSONLWALWriter."""

    def test_drains_rotated_files(self, tmp_path: str) -> None:
        """Sender drains records across rotated files, preserving order."""
        mgr = FileWALDirectoryManager(str(tmp_path))

        # Small max_file_size to force rotation.
        with JSONLWALWriter(mgr, max_file_size=50) as writer:
            for i in range(10):
                writer.write({"type": "obj_create", "seq": i})

        # Writer is closed — all lock files removed.
        received: list[WALRecord] = []
        sender = BackgroundWALSender(
            mgr, {"obj_create": received.append}, JSONLWALConsumer
        )
        sender.drain_once()

        assert len(received) == 10
        assert [r["seq"] for r in received] == list(range(10))
        assert mgr.list_files() == []

    def test_pid_lock_tracks_rotation(self, tmp_path: str) -> None:
        """PID lock follows the writer through file rotation."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = JSONLWALWriter(mgr, max_file_size=50)

        # Write enough to trigger rotation.
        for _ in range(5):
            writer.write({"type": "obj_create", "data": "x" * 20})

        # Multiple files exist; only the current one has a live lock.
        files = mgr.list_files()
        assert len(files) > 1
        active = writer.current_path
        for f in files:
            if f == active:
                assert is_writer_alive(f) is True
            else:
                # Rotated files had their lock removed on close.
                assert is_writer_alive(f) is False

        # Sender removes rotated files, keeps active one.
        received: list[WALRecord] = []
        sender = BackgroundWALSender(
            mgr, {"obj_create": received.append}, JSONLWALConsumer
        )
        sender.drain_once()

        assert len(mgr.list_files()) == 1
        assert mgr.list_files()[0] == active

        writer.close()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Background thread timing is unreliable on Windows CI runners",
    )
    def test_concurrent_write_and_drain(self, tmp_path: str) -> None:
        """Writer and sender operating concurrently (simulated cross-process)."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = JSONLWALWriter(mgr, max_file_size=100)
        total_records = 20

        received: list[WALRecord] = []
        all_received = threading.Event()

        def tracking_handler(record: WALRecord) -> None:
            received.append(record)
            if len(received) >= total_records:
                all_received.set()

        sender = BackgroundWALSender(
            mgr,
            {"obj_create": tracking_handler},
            JSONLWALConsumer,
            poll_interval=0.05,
        )
        sender.start()

        try:
            for i in range(total_records):
                writer.write({"type": "obj_create", "seq": i})

            writer.close()

            assert all_received.wait(timeout=5.0), (
                f"Sender only received {len(received)}/{total_records} records"
            )
            assert [r["seq"] for r in received] == list(range(total_records))
        finally:
            sender.stop()

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Background thread timing is unreliable on Windows CI runners",
    )
    def test_full_lifecycle_write_send_cleanup(self, tmp_path: str) -> None:
        """End-to-end: write with rotation, send via background thread, cleanup."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = JSONLWALWriter(mgr, max_file_size=80)

        calls: list[WALRecord] = []
        objs: list[WALRecord] = []
        handlers = {
            "call_start": calls.append,
            "call_end": calls.append,
            "obj_create": objs.append,
        }
        sender = BackgroundWALSender(
            mgr,
            handlers,
            JSONLWALConsumer,
            poll_interval=0.05,
        )
        sender.start()

        try:
            writer.write({"type": "call_start", "id": "c1", "op": "predict"})
            writer.write({"type": "obj_create", "digest": "sha256:abc"})
            writer.write({"type": "call_end", "id": "c1", "output": 42})

            writer.close()

            deadline = time.monotonic() + 2.0
            while (len(calls) < 2 or len(objs) < 1) and time.monotonic() < deadline:
                time.sleep(0.02)

            assert len(calls) == 2
            assert len(objs) == 1
            assert calls[0]["op"] == "predict"
            assert calls[1]["output"] == 42
            assert objs[0]["digest"] == "sha256:abc"
        finally:
            sender.stop()

        # After stop, all fully-consumed files are cleaned up.
        assert mgr.list_files() == []


class TestCrossProcessProtection:
    """Tests for PID-lock-based cross-process file protection."""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="PID reuse on Windows makes stale-PID detection unreliable",
    )
    def test_stale_pid_allows_deletion(self, tmp_path: str) -> None:
        """A lock file with a dead PID is treated as stale -> file deletable."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        path = mgr.list_files()[0]

        # Manually create a lock file with a dead PID.
        base, _ = os.path.splitext(path)
        lock_path = base + ".lock"
        with open(lock_path, "w", encoding="utf-8") as f:
            f.write("999999999")  # PID that (almost certainly) doesn't exist

        assert is_writer_alive(path) is False

        sender = BackgroundWALSender(
            mgr, {"obj_create": lambda r: None}, JSONLWALConsumer
        )
        sender.drain_once()
        assert mgr.list_files() == []

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Subprocess-based tests are unreliable on Windows CI runners",
    )
    def test_cross_process_writer_prevents_deletion(self, tmp_path: str) -> None:
        """A subprocess writing to a WAL file prevents the sender from deleting it."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        path = mgr.list_files()[0]

        # Spawn a subprocess that creates a lock file and stays alive.
        base, _ = os.path.splitext(path)
        lock_path = base + ".lock"
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import os, sys\n"
                    f"with open({lock_path!r}, 'w') as f:\n"
                    "    f.write(str(os.getpid()))\n"
                    "sys.stdout.write('ready\\n')\n"
                    "sys.stdout.flush()\n"
                    "sys.stdin.readline()\n"  # block until parent signals
                ),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        sender = BackgroundWALSender(
            mgr, {"obj_create": lambda r: None}, JSONLWALConsumer
        )
        try:
            assert proc.stdout is not None
            line = proc.stdout.readline()
            assert line.strip() == b"ready"

            assert is_writer_alive(path) is True

            sender.drain_once()

            # File should still exist — subprocess is alive.
            assert len(mgr.list_files()) == 1
        finally:
            assert proc.stdin is not None
            proc.stdin.write(b"done\n")
            proc.stdin.flush()
            proc.wait(timeout=5)

        # Subprocess exited — lock file has stale PID.
        assert is_writer_alive(path) is False

        # Same sender, second drain — consumer is cached, file now deletable.
        sender.drain_once()
        assert mgr.list_files() == []

    def test_custom_is_file_active(self, tmp_path: str) -> None:
        """A custom is_file_active callable overrides the default PID lock check."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        # Custom check that always says "active" → file never deleted.
        sender1 = BackgroundWALSender(
            mgr,
            {"obj_create": lambda r: None},
            JSONLWALConsumer,
            is_file_active=lambda path: True,
        )
        sender1.drain_once()
        assert len(mgr.list_files()) == 1
        sender1.stop()  # release cached consumers

        # Custom check that always says "not active" → file deleted.
        sender2 = BackgroundWALSender(
            mgr,
            {"obj_create": lambda r: None},
            JSONLWALConsumer,
            is_file_active=lambda path: False,
        )
        sender2.drain_once()
        assert mgr.list_files() == []


@pytest.fixture
def writer_subprocess():
    """Fixture that manages a WAL writer running in a child process.

    Returns a factory function:
        start(wal_dir, count, *, crash=False) -> subprocess.Popen

    The subprocess writes `count` records to the WAL directory.

    In normal mode, it signals "written" on stdout, then waits for a
    line on stdin before closing the writer and signaling "closed".

    In crash mode (crash=True), it writes records and exits immediately
    WITHOUT closing the writer, leaving a stale .lock file behind.

    All spawned processes are cleaned up on fixture teardown.
    """
    # Inline script executed via `python -c`.  We need a real subprocess
    # (not multiprocessing) because PID lock detection requires a
    # genuinely different OS PID.
    script = """\
import sys
from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.durability.wal_writer import JSONLWALWriter

wal_dir = sys.argv[1]
count = int(sys.argv[2])
crash = len(sys.argv) > 3 and sys.argv[3] == "--crash"

mgr = FileWALDirectoryManager(wal_dir)
writer = JSONLWALWriter(mgr)
for i in range(count):
    writer.write({"type": "obj_create", "seq": i})

if crash:
    sys.exit(0)

sys.stdout.write("written\\n")
sys.stdout.flush()
sys.stdin.readline()
writer.close()
sys.stdout.write("closed\\n")
sys.stdout.flush()
"""
    procs: list[subprocess.Popen] = []

    def start(wal_dir: str, count: int, *, crash: bool = False) -> subprocess.Popen:
        args = [sys.executable, "-c", script, wal_dir, str(count)]
        if crash:
            args.append("--crash")
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        procs.append(proc)
        return proc

    yield start

    for proc in procs:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)


class TestEndToEndCrossProcess:
    """Cross-process tests: writer in a subprocess, sender in test process.

    These tests use real separate processes (not multiprocessing.Process)
    because PID lock detection requires a genuinely different OS PID that
    becomes invalid when the process exits.  This is the standard pattern
    for cross-process testing in Python — CPython's own test suite uses
    subprocess.Popen for the same reason.

    The writer subprocess logic is defined as an inline script in the
    ``writer_subprocess`` fixture above.
    """

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Subprocess-based tests are unreliable on Windows CI runners",
    )
    def test_sender_drains_records_from_writer_subprocess(
        self, tmp_path: str, writer_subprocess
    ) -> None:
        """Sender in this process reads records written by a subprocess."""
        wal_dir = str(tmp_path)

        proc = writer_subprocess(wal_dir, _SUBPROCESS_RECORD_COUNT)

        # Wait for the writer to finish writing.
        assert proc.stdout is not None
        line = proc.stdout.readline()
        assert line.strip() == b"written"

        # Writer is still open → lock file protects the WAL file.
        mgr = FileWALDirectoryManager(wal_dir)
        files = mgr.list_files()
        assert len(files) == 1
        assert is_writer_alive(files[0]) is True

        # Sender drains the records but can't delete the file.
        received: list[WALRecord] = []
        sender = BackgroundWALSender(
            mgr,
            {"obj_create": received.append},
            JSONLWALConsumer,
        )
        sender.drain_once()

        assert len(received) == _SUBPROCESS_RECORD_COUNT
        assert [r["seq"] for r in received] == list(range(_SUBPROCESS_RECORD_COUNT))
        # File still exists — writer subprocess is alive.
        assert len(mgr.list_files()) == 1

        # Tell the writer to close.
        assert proc.stdin is not None
        proc.stdin.write(b"go\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        assert line.strip() == b"closed"
        proc.wait(timeout=5)

        # Writer closed → lock removed → sender can delete.
        assert is_writer_alive(mgr.list_files()[0]) is False
        sender.drain_once()
        assert mgr.list_files() == []

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Subprocess-based tests are unreliable on Windows CI runners",
    )
    def test_sender_recovers_after_writer_crash(
        self, tmp_path: str, writer_subprocess
    ) -> None:
        """Writer subprocess exits without closing → stale .lock file.
        Sender detects the dead PID and cleans up.
        """
        wal_dir = str(tmp_path)

        proc = writer_subprocess(wal_dir, _SUBPROCESS_RECORD_COUNT, crash=True)
        proc.wait(timeout=5)
        assert proc.returncode == 0

        # Lock file exists but PID is dead → stale.
        mgr = FileWALDirectoryManager(wal_dir)
        files = mgr.list_files()
        assert len(files) == 1
        assert is_writer_alive(files[0]) is False

        # Sender drains and cleans up.
        received: list[WALRecord] = []
        sender = BackgroundWALSender(
            mgr,
            {"obj_create": received.append},
            JSONLWALConsumer,
        )
        sender.drain_once()

        assert len(received) == _SUBPROCESS_RECORD_COUNT
        assert [r["seq"] for r in received] == list(range(_SUBPROCESS_RECORD_COUNT))
        assert mgr.list_files() == []


class TestRegressions:
    """Regression tests for specific bugs."""

    def test_lock_exists_before_wal_file_is_discoverable(
        self, tmp_path: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lock sidecar must exist before the .jsonl file so the sender
        never sees a WAL file without its liveness marker.

        Regression: previously the writer opened the .jsonl first and
        created the lock second.  A sender polling in between would see
        an "inactive" file and delete it.
        """
        from unittest.mock import patch

        from weave.durability import wal_writer as wmod
        from weave.durability.wal_lock import acquire_lock

        call_order: list[str] = []
        original_open = open

        # Patch open() to record when the .jsonl is opened.
        def tracking_open(path: str, *args, **kwargs):  # type: ignore[no-untyped-def]
            if isinstance(path, str) and path.endswith(".jsonl"):
                call_order.append("open_jsonl")
            return original_open(path, *args, **kwargs)

        # Patch acquire_lock to record when the lock is created.
        def tracking_acquire(path: str) -> str:
            call_order.append("acquire_lock")
            return acquire_lock(path)

        with (
            patch("builtins.open", side_effect=tracking_open),
            patch.object(wmod, "acquire_lock", side_effect=tracking_acquire),
        ):
            mgr = FileWALDirectoryManager(str(tmp_path))
            writer = mgr.create_file()
            writer.close()

        assert call_order.index("acquire_lock") < call_order.index("open_jsonl"), (
            f"Lock must be acquired before .jsonl is opened, but got: {call_order}"
        )

    def test_stop_raises_on_timeout(self, tmp_path: str) -> None:
        """stop() raises TimeoutError if the thread doesn't die in time,
        and leaves _thread intact so start() still rejects.

        Regression: previously stop() cleared _thread unconditionally,
        allowing a second start() while the first thread was still alive.
        """
        block = threading.Event()

        def blocking_handler(record: WALRecord) -> None:
            block.wait(timeout=10)

        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        sender = BackgroundWALSender(
            mgr,
            {"obj_create": blocking_handler},
            JSONLWALConsumer,
            is_file_active=lambda _: False,
        )
        sender.start()
        # Give the thread time to enter the blocking handler.
        time.sleep(0.1)

        with pytest.raises(TimeoutError, match="did not stop"):
            sender.stop(timeout=0.01)

        # _thread is still set — start() must reject.
        assert sender._thread is not None
        with pytest.raises(RuntimeError, match="already running"):
            sender.start()

        # Unblock and let it finish cleanly.
        block.set()
        sender._thread.join(timeout=5)
        sender._thread = None
