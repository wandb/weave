"""Tests for WAL directory namespacing by API key.

Covers:
- WALManager places files in api_key-specific subdirectories
- Two different API keys get isolated directories
- A new sender with the same API key recovers orphaned files (crash recovery)
- A sender with a different API key does NOT see another key's files
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

from weave.durability.wal_client_id import compute_client_id
from weave.durability.wal_manager import WALManager
from weave.durability.wal_sender import create_sender
from weave.trace_server import trace_server_interface as tsi


class TestWALDirectoryNamespacing:
    """Verify that WALManager uses api_key-based subdirectory."""

    def test_wal_manager_with_api_key_adds_subdirectory(self, tmp_path):
        mgr = WALManager("my-entity", "my-project", api_key="wk-abc123")
        # Should have a subdirectory beyond entity/project
        assert "my-entity" in mgr.wal_dir
        assert "my-project" in mgr.wal_dir
        parts = mgr.wal_dir.split(os.sep)
        project_idx = parts.index("my-project")
        assert len(parts) > project_idx + 1  # there's a subdirectory after project

    def test_wal_manager_without_api_key_unchanged(self, tmp_path):
        mgr = WALManager("my-entity", "my-project")
        assert mgr.wal_dir.endswith(os.path.join("my-entity", "my-project"))
        assert not mgr.wal_dir.endswith(os.sep)

    def test_two_api_keys_get_isolated_directories(self, tmp_path):
        """Two different API keys writing to the same entity/project get separate dirs."""
        mgr_a = WALManager("entity", "project", api_key="wk-key-aaa")
        mgr_b = WALManager("entity", "project", api_key="wk-key-bbb")

        assert mgr_a.wal_dir != mgr_b.wal_dir

    def test_same_api_key_gets_same_directory(self, tmp_path):
        """Same API key always resolves to the same WAL directory."""
        mgr_a = WALManager("entity", "project", api_key="wk-key-aaa")
        mgr_b = WALManager("entity", "project", api_key="wk-key-aaa")

        assert mgr_a.wal_dir == mgr_b.wal_dir


class TestCrashRecovery:
    """End-to-end: orphaned WAL files are recovered by a new process with the same API key."""

    def test_new_sender_picks_up_orphaned_wal_files(self, tmp_path, monkeypatch):
        """Simulate: process A writes records and dies, process B starts with
        the same API key and its sender drains the orphaned files.
        """
        # Point WAL_ROOT at tmp_path so we don't touch the real ~/.weave/wal
        fake_wal_root = str(tmp_path / "wal_root")
        monkeypatch.setattr("weave.durability.wal_client_id.WAL_ROOT", fake_wal_root)
        monkeypatch.setattr("weave.durability.wal_manager.WAL_ROOT", fake_wal_root)

        api_key = "wk-crash-recovery-test"

        # --- Process A: write records, then "crash" (close writer only) ---
        mgr_a = WALManager("entity", "project", api_key=api_key)
        mgr_a.write(
            "obj_create",
            tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id="entity/project",
                    object_id="orphaned_obj",
                    val={"rescued": True},
                )
            ),
        )
        mgr_a.flush()
        wal_dir = mgr_a.wal_dir
        # Close writer (releases lock file) but don't drain — simulates crash
        mgr_a.close()

        # Verify the WAL file is still on disk
        jsonl_files = [f for f in os.listdir(wal_dir) if f.endswith(".jsonl")]
        assert len(jsonl_files) == 1

        # --- Process B: same API key, compute the wal_dir and create a sender ---
        # Don't create a full WALManager (that would create a new writer file).
        # Just verify the directory resolves the same and point a sender at it.
        recovered_client_id = compute_client_id(api_key)
        recovered_wal_dir = os.path.join(
            fake_wal_root, "entity", "project", recovered_client_id
        )
        assert recovered_wal_dir == wal_dir

        mock_server = MagicMock()
        sender = create_sender(recovered_wal_dir, mock_server, poll_interval=0.1)
        sender.start()
        sender.stop()  # stop() does a final drain

        # The sender should have called obj_create on the mock server
        mock_server.obj_create.assert_called_once()
        call_arg = mock_server.obj_create.call_args[0][0]
        assert isinstance(call_arg, tsi.ObjCreateReq)
        assert call_arg.obj.object_id == "orphaned_obj"

        # The WAL file should be cleaned up after draining
        remaining = [f for f in os.listdir(wal_dir) if f.endswith(".jsonl")]
        assert len(remaining) == 0

    def test_different_api_key_does_not_see_other_keys_files(
        self, tmp_path, monkeypatch
    ):
        """A sender with api_key B must NOT drain files written by api_key A."""
        fake_wal_root = str(tmp_path / "wal_root")
        monkeypatch.setattr("weave.durability.wal_client_id.WAL_ROOT", fake_wal_root)
        monkeypatch.setattr("weave.durability.wal_manager.WAL_ROOT", fake_wal_root)

        # --- Writer A ---
        mgr_a = WALManager("entity", "project", api_key="wk-key-aaa")
        mgr_a.write(
            "obj_create",
            tsi.ObjCreateReq(
                obj=tsi.ObjSchemaForInsert(
                    project_id="entity/project",
                    object_id="secret_obj",
                    val={"owner": "A"},
                )
            ),
        )
        mgr_a.flush()
        mgr_a.close()

        # --- Sender B (different key) ---
        mock_server = MagicMock()
        mgr_b = WALManager("entity", "project", api_key="wk-key-bbb")
        assert mgr_b.wal_dir != mgr_a.wal_dir  # different directories

        sender = create_sender(mgr_b.wal_dir, mock_server, poll_interval=0.1)
        sender.start()
        sender.stop()

        # B's sender should NOT have called anything — A's files are in a different dir
        mock_server.obj_create.assert_not_called()

        mgr_b.close()
