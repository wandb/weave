from __future__ import annotations

import os

from weave.durability.wal_directory_manager import FileWALDirectoryManager


class TestFileWALDirectoryManager:
    def test_create_file_creates_directory(self, tmp_path: str) -> None:
        """create_file() creates the WAL directory (including parents) if needed."""
        subdir = os.path.join(str(tmp_path), "new", "nested")
        mgr = FileWALDirectoryManager(subdir)

        with mgr.create_file():
            assert os.path.isdir(subdir)

    def test_created_file_exists_on_disk(self, tmp_path: str) -> None:
        """The .jsonl file exists immediately, even before any records are written."""
        mgr = FileWALDirectoryManager(str(tmp_path))

        with mgr.create_file():
            jsonl_files = [f for f in os.listdir(str(tmp_path)) if f.endswith(".jsonl")]
            assert len(jsonl_files) == 1

    def test_list_files_empty_or_missing(self, tmp_path: str) -> None:
        """Returns [] when the directory is empty or doesn't exist yet."""
        mgr_empty = FileWALDirectoryManager(str(tmp_path))
        assert mgr_empty.list_files() == []

        mgr_missing = FileWALDirectoryManager(os.path.join(str(tmp_path), "nope"))
        assert mgr_missing.list_files() == []

    def test_list_files_returns_relevant_paths(self, tmp_path: str) -> None:
        """Returns only WAL files, ignoring checkpoints and other artifacts."""
        for name in ["aaa.jsonl", "bbb.jsonl", "aaa.checkpoint", "notes.txt"]:
            open(os.path.join(str(tmp_path), name), "w", encoding="utf-8").close()

        mgr = FileWALDirectoryManager(str(tmp_path))
        files = mgr.list_files()

        assert len(files) == 2
        assert all(f.endswith(".jsonl") for f in files)

    def test_list_files_sorted_oldest_first(self, tmp_path: str) -> None:
        """Files are returned oldest-first via timestamp-prefixed filenames."""
        # Simulate two files with timestamp prefixes — alphabetical order
        # matches chronological order because the prefix is zero-padded.
        old_path = os.path.join(str(tmp_path), "00000000000000001000_aaa.jsonl")
        new_path = os.path.join(str(tmp_path), "00000000000000002000_bbb.jsonl")
        open(old_path, "w", encoding="utf-8").close()
        open(new_path, "w", encoding="utf-8").close()

        mgr = FileWALDirectoryManager(str(tmp_path))
        files = mgr.list_files()

        assert files[0] == old_path
        assert files[1] == new_path

    def test_remove_deletes_file_and_checkpoint(self, tmp_path: str) -> None:
        """remove() deletes both the .jsonl file and its .checkpoint sidecar."""
        jsonl_path = os.path.join(str(tmp_path), "test.jsonl")
        checkpoint_path = os.path.join(str(tmp_path), "test.checkpoint")
        open(jsonl_path, "w", encoding="utf-8").close()
        open(checkpoint_path, "w", encoding="utf-8").close()

        mgr = FileWALDirectoryManager(str(tmp_path))
        mgr.remove(jsonl_path)

        assert not os.path.exists(jsonl_path)
        assert not os.path.exists(checkpoint_path)

    def test_remove_nonexistent_does_not_raise(self, tmp_path: str) -> None:
        """remove() is idempotent — missing files don't raise."""
        mgr = FileWALDirectoryManager(str(tmp_path))
        mgr.remove(os.path.join(str(tmp_path), "ghost.jsonl"))
