import os

import pytest

from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact


def test_mem_artifact_path_sanitization():
    art = MemTraceFilesArtifact(
        path_contents={
            "audio.wav": b"RIFF",
            "subdir/file.txt": b"nested",
            "/etc/passwd": b"abs",
            "../../etc/shadow": b"traversal",
        }
    )

    # Valid relative paths work, including nested
    assert art.path("audio.wav").endswith("audio.wav")
    result = art.path("subdir/file.txt")
    assert result.endswith(os.path.join("subdir", "file.txt"))

    # Absolute paths rejected
    with pytest.raises(ValueError, match="absolute path"):
        art.path("/etc/passwd")
    with pytest.raises(ValueError, match="absolute path"):
        art.path("audio.wav", filename="/tmp/evil.pth")

    # Traversals rejected
    with pytest.raises(ValueError, match="escapes base directory"):
        art.path("../../etc/shadow")

    # writeable_file_path: valid works, absolute and traversal rejected
    with art.writeable_file_path("output.wav") as fp:
        with open(fp, "wb") as f:
            f.write(b"data")
    assert art.path_contents["output.wav"] == b"data"

    with pytest.raises(ValueError, match="absolute path"):
        with art.writeable_file_path("/etc/evil"):
            pass
    with pytest.raises(ValueError, match="escapes base directory"):
        with art.writeable_file_path("../../etc/evil"):
            pass
