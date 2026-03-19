from __future__ import annotations

import json
import subprocess
import sys
import time

import pytest

from weave.durability.wal import WALRecord
from weave.durability.wal_consumer import JSONLWALConsumer
from weave.durability.wal_directory_manager import FileWALDirectoryManager
from weave.durability.wal_sender import WALSender, _is_file_locked
from weave.durability.wal_writer import JSONLWALWriter

try:
    import fcntl

    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False


class TestDrainOnce:
    """Tests for WALSender.drain_once() without the background thread."""

    def test_delivers_records_to_handler(self, tmp_path: str) -> None:
        """drain_once() reads pending records and dispatches to handlers."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "call_start", "id": "c1"})
            writer.write({"type": "call_end", "id": "c1"})

        received: list[WALRecord] = []
        handlers = {"call_start": received.append, "call_end": received.append}
        sender = WALSender(mgr, handlers, JSONLWALConsumer)
        count = sender.drain_once()

        assert count == 2
        assert received[0] == {"type": "call_start", "id": "c1"}
        assert received[1] == {"type": "call_end", "id": "c1"}

    def test_removes_completed_files_not_in_active_set(self, tmp_path: str) -> None:
        """Fully-consumed files outside the active set are removed."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as w1:
            w1.write({"type": "obj_create", "seq": 0})
        # Second file is the "active" one (writer still open).
        w2 = mgr.create_file()
        w2.write({"type": "obj_create", "seq": 1})
        w2.flush()

        assert len(mgr.list_files()) == 2

        received: list[WALRecord] = []
        sender = WALSender(
            mgr,
            {"obj_create": received.append},
            JSONLWALConsumer,
            active_paths=lambda: {w2.path},
        )
        sender.drain_once()

        # First file (not active) removed; second file (active) kept.
        assert len(mgr.list_files()) == 1
        assert len(received) == 2

        w2.close()

    def test_protects_active_file_from_deletion(self, tmp_path: str) -> None:
        """A file in the active set is never removed, even if fully consumed."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = mgr.create_file()
        writer.write({"type": "obj_create", "seq": 0})
        writer.flush()

        sender = WALSender(
            mgr,
            {"obj_create": lambda r: None},
            JSONLWALConsumer,
            active_paths=lambda: {writer.path},
        )
        sender.drain_once()

        # File is protected — still present even though fully consumed.
        assert len(mgr.list_files()) == 1

        writer.close()

    def test_removes_all_when_no_active_paths(self, tmp_path: str) -> None:
        """With no active_paths, all fully-consumed files are removed."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        sender = WALSender(mgr, {"obj_create": lambda r: None}, JSONLWALConsumer)
        sender.drain_once()

        assert mgr.list_files() == []

    def test_active_path_none_is_ignored(self, tmp_path: str) -> None:
        """None values in the active_paths set are safely ignored.

        After writer.close(), active_path returns None.  The sender
        must not treat None as a real path to protect.
        """
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = JSONLWALWriter(mgr)
        writer.write({"type": "obj_create", "seq": 0})
        writer.close()  # active_path is now None

        sender = WALSender(
            mgr,
            {"obj_create": lambda r: None},
            JSONLWALConsumer,
            active_paths=lambda: {writer.active_path},  # {None}
        )
        sender.drain_once()

        # None is filtered out — file should be removed.
        assert mgr.list_files() == []

    def test_empty_directory_is_noop(self, tmp_path: str) -> None:
        """No WAL files means drain_once returns 0 without errors."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        sender = WALSender(mgr, {}, JSONLWALConsumer)
        assert sender.drain_once() == 0

    def test_multiple_drain_cycles(self, tmp_path: str) -> None:
        """Records written between drain cycles are picked up."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = mgr.create_file()

        received: list[WALRecord] = []
        sender = WALSender(
            mgr,
            {"obj_create": received.append},
            JSONLWALConsumer,
            active_paths=lambda: {writer.path},
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

    def test_flush_is_synchronous(self, tmp_path: str) -> None:
        """flush() drains records synchronously on the caller's thread."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        received: list[WALRecord] = []
        sender = WALSender(mgr, {"obj_create": received.append}, JSONLWALConsumer)

        count = sender.flush()
        assert count == 1
        assert len(received) == 1


class TestBackgroundThread:
    """Tests for the background drain thread."""

    def test_start_and_stop(self, tmp_path: str) -> None:
        """Sender starts a thread and stops cleanly."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        sender = WALSender(mgr, {}, JSONLWALConsumer, poll_interval=0.05)

        sender.start()
        assert sender._thread is not None
        assert sender._thread.is_alive()

        sender.stop()
        assert sender._thread is None

    def test_start_twice_raises(self, tmp_path: str) -> None:
        """Starting the sender twice raises RuntimeError."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        sender = WALSender(mgr, {}, JSONLWALConsumer, poll_interval=0.05)

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

        received: list[WALRecord] = []
        sender = WALSender(
            mgr,
            {"obj_create": received.append},
            JSONLWALConsumer,
            poll_interval=0.05,
            active_paths=lambda: {writer.path},
        )
        sender.start()

        try:
            writer.write({"type": "obj_create", "seq": 0})
            writer.flush()

            # Wait for the background thread to pick it up.
            deadline = time.monotonic() + 2.0
            while not received and time.monotonic() < deadline:
                time.sleep(0.02)

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
        sender = WALSender(
            mgr,
            {"obj_create": received.append},
            JSONLWALConsumer,
            poll_interval=60.0,
            active_paths=lambda: {writer.active_path},
        )
        # Long poll interval ensures the background thread won't drain
        # during the window between write and stop.
        sender.start()

        writer.write({"type": "obj_create", "seq": 0})

        # Close writer first → active_path becomes None → file unprotected.
        writer.close()
        sender.stop()

        assert len(received) == 1
        assert received[0]["seq"] == 0
        # Final drain should clean up since writer is closed.
        assert mgr.list_files() == []

    def test_context_manager(self, tmp_path: str) -> None:
        """WALSender can be used as a context manager."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        received: list[WALRecord] = []
        with WALSender(
            mgr, {"obj_create": received.append}, JSONLWALConsumer, poll_interval=0.05
        ):
            deadline = time.monotonic() + 2.0
            while not received and time.monotonic() < deadline:
                time.sleep(0.02)

        assert len(received) == 1


class TestCrashRecovery:
    """Tests simulating crash recovery scenarios."""

    def test_drains_orphaned_files(self, tmp_path: str) -> None:
        """Files from crashed processes are drained and cleaned up."""
        mgr = FileWALDirectoryManager(str(tmp_path))

        # Simulate two crashed processes that left WAL files.
        with mgr.create_file() as w1:
            w1.write({"type": "call_start", "id": "orphan-1"})
        with mgr.create_file() as w2:
            w2.write({"type": "call_start", "id": "orphan-2"})
            w2.write({"type": "call_end", "id": "orphan-2"})

        received: list[WALRecord] = []
        handlers = {"call_start": received.append, "call_end": received.append}
        # No active_paths — all files are orphans, safe to remove.
        sender = WALSender(mgr, handlers, JSONLWALConsumer)
        sender.drain_once()

        assert len(received) == 3
        assert mgr.list_files() == []

    def test_interleaved_crash_recovery_and_new_writes(
        self, tmp_path: str
    ) -> None:
        """Orphaned files are cleaned up while new writes continue."""
        mgr = FileWALDirectoryManager(str(tmp_path))

        # Orphaned file from a "crashed" process.
        with mgr.create_file() as orphan:
            orphan.write({"type": "call_start", "id": "old"})

        # New writer for the current process.
        writer = mgr.create_file()
        writer.write({"type": "call_start", "id": "new"})
        writer.flush()

        received: list[WALRecord] = []
        sender = WALSender(
            mgr,
            {"call_start": received.append},
            JSONLWALConsumer,
            active_paths=lambda: {writer.path},
        )
        sender.drain_once()

        # Both records processed.
        assert len(received) == 2
        # Orphaned file removed, active writer's file protected.
        assert len(mgr.list_files()) == 1

        writer.close()


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

        sender = WALSender(mgr, {"obj_create": handler}, JSONLWALConsumer)
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
        # Protect the file so drain doesn't remove it (and its sidecars).
        sender = WALSender(
            mgr,
            {"obj_create": handler},
            JSONLWALConsumer,
            active_paths=lambda: {path},
        )
        sender.drain_once()

        # Check the dead-letter file for the failed record.
        base = path.rsplit(".", 1)[0]
        dead_letter_path = base + ".deadletter"
        with open(dead_letter_path, encoding="utf-8") as f:
            dead = [json.loads(line) for line in f]
        assert len(dead) == 1
        assert dead[0]["seq"] == 1

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

        sender = WALSender(
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
    """Tests combining WALSender with the rotating JSONLWALWriter."""

    def test_drains_rotated_files(self, tmp_path: str) -> None:
        """Sender drains records across rotated files, preserving order."""
        mgr = FileWALDirectoryManager(str(tmp_path))

        # Small max_file_size to force rotation.
        with JSONLWALWriter(mgr, max_file_size=50) as writer:
            for i in range(10):
                writer.write({"type": "obj_create", "seq": i})

        # Writer is closed — no active paths to protect.
        received: list[WALRecord] = []
        sender = WALSender(mgr, {"obj_create": received.append}, JSONLWALConsumer)
        sender.drain_once()

        assert len(received) == 10
        assert [r["seq"] for r in received] == list(range(10))
        assert mgr.list_files() == []

    def test_active_path_tracks_rotation(self, tmp_path: str) -> None:
        """active_path follows the writer through file rotation."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = JSONLWALWriter(mgr, max_file_size=50)

        path_before = writer.active_path
        # Write enough to trigger rotation.
        for _ in range(5):
            writer.write({"type": "obj_create", "data": "x" * 20})
        path_after = writer.active_path

        # Rotation happened — active path changed.
        assert path_before != path_after
        assert path_after is not None

        # Sender protects only the current active file.
        received: list[WALRecord] = []
        sender = WALSender(
            mgr,
            {"obj_create": received.append},
            JSONLWALConsumer,
            active_paths=lambda: {writer.active_path},
        )
        files_before = len(mgr.list_files())
        sender.drain_once()

        # Rotated (non-active) files removed; active file kept.
        assert len(mgr.list_files()) == 1
        assert mgr.list_files()[0] == path_after
        assert files_before > 1  # rotation did happen

        writer.close()

    def test_concurrent_write_and_drain(self, tmp_path: str) -> None:
        """Writer and sender operating concurrently."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        writer = JSONLWALWriter(mgr, max_file_size=100)

        received: list[WALRecord] = []
        sender = WALSender(
            mgr,
            {"obj_create": received.append},
            JSONLWALConsumer,
            poll_interval=0.05,
            active_paths=lambda: {writer.active_path},
        )
        sender.start()

        try:
            for i in range(20):
                writer.write({"type": "obj_create", "seq": i})
                time.sleep(0.01)

            writer.close()

            # Wait for the sender to catch up.
            deadline = time.monotonic() + 5.0
            while len(received) < 20 and time.monotonic() < deadline:
                time.sleep(0.05)

            assert len(received) == 20
            assert [r["seq"] for r in received] == list(range(20))
        finally:
            sender.stop()

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
        sender = WALSender(
            mgr,
            handlers,
            JSONLWALConsumer,
            poll_interval=0.05,
            active_paths=lambda: {writer.active_path},
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


@pytest.mark.skipif(not _HAS_FLOCK, reason="flock not available on this platform")
class TestCrossProcessProtection:
    """Tests for flock-based cross-process file protection."""

    def test_locked_file_not_deleted(self, tmp_path: str) -> None:
        """Sender won't delete a file locked by another process."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        path = mgr.list_files()[0]

        # Spawn a subprocess that holds an exclusive flock on the file.
        # It reads a line from stdin to stay alive, then exits.
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import fcntl, sys\n"
                    f"f = open({path!r}, 'rb')\n"
                    "fcntl.flock(f, fcntl.LOCK_EX)\n"
                    "sys.stdout.write('locked\\n')\n"
                    "sys.stdout.flush()\n"
                    "sys.stdin.readline()\n"  # block until parent signals
                ),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
        )
        try:
            # Wait for the subprocess to confirm it holds the lock.
            assert proc.stdout is not None
            line = proc.stdout.readline()
            assert line.strip() == b"locked"

            assert _is_file_locked(path) is True

            # Sender has NO active_paths — relies purely on flock.
            sender = WALSender(
                mgr, {"obj_create": lambda r: None}, JSONLWALConsumer
            )
            sender.drain_once()

            # File should still exist — subprocess holds the lock.
            assert len(mgr.list_files()) == 1
        finally:
            # Tell subprocess to exit, releasing the lock.
            assert proc.stdin is not None
            proc.stdin.write(b"done\n")
            proc.stdin.flush()
            proc.wait(timeout=5)

        # Now that the lock is released, the file can be deleted.
        assert _is_file_locked(path) is False
        sender = WALSender(mgr, {"obj_create": lambda r: None}, JSONLWALConsumer)
        sender.drain_once()
        assert mgr.list_files() == []

    def test_unlocked_file_is_deleted(self, tmp_path: str) -> None:
        """After writer closes (releasing flock), file can be deleted."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        path = mgr.list_files()[0]

        # Writer is closed — flock is released.
        assert _is_file_locked(path) is False

        sender = WALSender(mgr, {"obj_create": lambda r: None}, JSONLWALConsumer)
        sender.drain_once()

        assert mgr.list_files() == []

    def test_missing_file_is_not_locked(self, tmp_path: str) -> None:
        """_is_file_locked returns False for a nonexistent file."""
        assert _is_file_locked(str(tmp_path / "nonexistent.jsonl")) is False

    def test_crashed_process_releases_lock(self, tmp_path: str) -> None:
        """When a process crashes, the OS releases its flock automatically."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        with mgr.create_file() as writer:
            writer.write({"type": "obj_create", "seq": 0})

        path = mgr.list_files()[0]

        # Spawn a subprocess that locks the file then exits abruptly.
        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                (
                    "import fcntl, sys\n"
                    f"f = open({path!r}, 'rb')\n"
                    "fcntl.flock(f, fcntl.LOCK_EX)\n"
                    "sys.stdout.write('locked\\n')\n"
                    "sys.stdout.flush()\n"
                    # Exit immediately — OS releases the lock.
                ),
            ],
            stdout=subprocess.PIPE,
        )
        assert proc.stdout is not None
        proc.stdout.readline()  # wait for lock to be acquired
        proc.wait(timeout=5)  # wait for process to exit

        # Process exited — lock should be released.
        assert _is_file_locked(path) is False

        sender = WALSender(mgr, {"obj_create": lambda r: None}, JSONLWALConsumer)
        sender.drain_once()
        assert mgr.list_files() == []
