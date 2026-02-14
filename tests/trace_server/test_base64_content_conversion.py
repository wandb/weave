"""Tests for content conversion: base64/data-URI detection, Content object storage,
and large-string offloading to file storage.
"""

import base64
import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from weave.trace_server.base64_content_conversion import (
    AUTO_CONVERSION_MIN_SIZE,
    is_base64,
    is_data_uri,
    process_call_req_to_content,
    replace_base64_with_content_objects,
    replace_large_strings_with_content_objects,
    store_content_object,
)
from weave.trace_server.trace_server_interface import (
    CallEndReq,
    CallStartReq,
    EndedCallSchemaForInsert,
    FileCreateRes,
    StartedCallSchemaForInsert,
)
from weave.type_wrappers.Content.content import Content

LARGE_TEST_DATA_SIZE = AUTO_CONVERSION_MIN_SIZE + 10
_TEST_MIN_BYTES = 100


def _mock_ts(num_files: int = 2) -> MagicMock:
    """Return a mock trace server whose file_create returns sequential digests."""
    ts = MagicMock()
    ts.file_create = MagicMock(
        side_effect=[FileCreateRes(digest=f"digest_{i}") for i in range(num_files)]
    )
    return ts


def _is_content_ref(val: object) -> bool:
    """True if val looks like a stored Content object reference dict."""
    return (
        isinstance(val, dict)
        and val.get("_type") == "CustomWeaveType"
        and val.get("weave_type", {}).get("type")
        == "weave.type_wrappers.Content.content.Content"
        and set(val.get("files", {}).keys()) == {"content", "metadata.json"}
    )


# ---------------------------------------------------------------------------
# Base64 / data-URI detection, storage, and replacement
# ---------------------------------------------------------------------------


def test_base64_and_data_uri_content_conversion():
    """End-to-end: detection heuristics, Content storage, replacement in dicts/lists,
    process_call_req_to_content, and standalone base64 edge cases.
    """
    # -- data-URI detection --
    b64_hello = base64.b64encode(b"Hello, World!").decode("ascii")
    assert is_data_uri(f"data:text/plain;base64,{b64_hello}")
    assert not is_data_uri("not a data uri")
    assert not is_data_uri("data:text/plain,not base64")

    # -- store_content_object structure --
    ts = _mock_ts()
    content_obj = Content.from_bytes(b"Test content")
    result = store_content_object(content_obj, "test_project", ts)

    assert _is_content_ref(result)
    assert result["files"]["content"] == "digest_0"
    assert result["files"]["metadata.json"] == "digest_1"
    assert ts.file_create.call_count == 2

    # first call stores raw content bytes, second stores metadata JSON
    content_call = ts.file_create.call_args_list[0][0][0]
    assert content_call.project_id == "test_project"
    assert content_call.content == b"Test content"
    metadata = json.loads(ts.file_create.call_args_list[1][0][0].content)
    assert metadata["mimetype"] == content_obj.mimetype

    # -- replace in dicts: data URIs converted, raw base64 left alone --
    ts = _mock_ts(num_files=4)
    big = b"a" * LARGE_TEST_DATA_SIZE
    b64_big = base64.b64encode(big).decode("ascii")

    out = replace_base64_with_content_objects(
        {
            "plain": "normal string",
            "raw_b64": b64_big,  # standalone base64 -> NOT replaced
            "nested": {"uri": f"data:image/png;base64,{b64_big}"},
        },
        "proj",
        ts,
    )
    assert out["plain"] == "normal string"
    assert out["raw_b64"] == b64_big  # raw base64 stays as-is
    assert _is_content_ref(out["nested"]["uri"])

    # -- replace in lists --
    ts = _mock_ts(num_files=4)
    out = replace_base64_with_content_objects(
        ["keep", b64_big, {"k": f"data:text/plain;base64,{b64_big}"}],
        "proj",
        ts,
    )
    assert out[0] == "keep"
    assert out[1] == b64_big  # raw base64 unchanged
    assert _is_content_ref(out[2]["k"])

    # -- process_call_req_to_content for CallStartReq and CallEndReq --
    ts = _mock_ts(num_files=4)
    start_req = CallStartReq(
        start=StartedCallSchemaForInsert(
            project_id="proj",
            op_name="op",
            started_at=datetime.utcnow(),
            attributes={},
            inputs={
                "image": f"data:image/png;base64,{b64_big}",
                "text": "Some normal text",
            },
        )
    )
    processed = process_call_req_to_content(start_req, ts)
    assert processed.start.inputs["text"] == "Some normal text"
    assert _is_content_ref(processed.start.inputs["image"])

    long_b64 = base64.b64encode(b"y" * LARGE_TEST_DATA_SIZE).decode("ascii")
    end_req = CallEndReq(
        end=EndedCallSchemaForInsert(
            project_id="proj",
            id="call-id",
            ended_at=datetime.utcnow(),
            summary={"usage": {}, "status_counts": {}},
            output=long_b64,
        )
    )
    processed_end = process_call_req_to_content(end_req, ts)
    assert processed_end.end.output == long_b64  # raw b64, not a data URI

    # -- non-media base64 strings stay untouched --
    ts = MagicMock()
    for b64_str in ("aaaa", "aGVsbG8=", "dGVzdCBtZXNzYWdl", "YQ==", "SGVsbG8gV29ybGQh"):
        assert is_base64(b64_str)
        r = replace_base64_with_content_objects({"f": b64_str}, "proj", ts)
        assert r["f"] == b64_str  # text/plain or octet-stream -> skip
    assert ts.file_create.call_count == 0

    # -- WAV-file base64 IS converted (audio mimetype detected) --
    ts = _mock_ts(num_files=2)
    wav = _build_minimal_wav(LARGE_TEST_DATA_SIZE)
    wav_b64 = base64.b64encode(wav).decode("ascii")
    assert is_base64(wav_b64)

    out = replace_base64_with_content_objects(
        {"audio": wav_b64, "label": "ok"}, "proj", ts
    )
    assert _is_content_ref(out["audio"])
    assert out["label"] == "ok"
    wav_meta = json.loads(ts.file_create.call_args_list[1][0][0].content)
    assert wav_meta["mimetype"] in ("audio/wav", "audio/x-wav", "audio/wave")


# ---------------------------------------------------------------------------
# Large-string offloading (replace_large_strings_with_content_objects)
# ---------------------------------------------------------------------------


def test_large_string_offloading():
    """Covers threshold behaviour, recursion into nested structures, non-string
    passthrough, metadata correctness, and graceful failure.
    """
    threshold = _TEST_MIN_BYTES
    large = "x" * (threshold + 1)
    small = "x" * (threshold - 1)
    exact = "x" * threshold

    # -- basic threshold: large converted, small/exact untouched --
    ts = _mock_ts(num_files=2)
    r = replace_large_strings_with_content_objects(
        {"lg": large, "sm": small, "eq": exact}, "proj", ts, min_chars=threshold
    )
    assert _is_content_ref(r["lg"])
    assert r["sm"] == small  # below threshold
    assert r["eq"] == exact  # at threshold (not strictly greater)
    assert ts.file_create.call_count == 2  # 1 content + 1 metadata

    # -- nested dicts and lists --
    ts = _mock_ts(num_files=6)
    deep = "y" * (threshold + 1)
    r = replace_large_strings_with_content_objects(
        {"outer": {"inner": deep, "sib": "short"}, "list": ["tiny", deep]},
        "proj",
        ts,
        min_chars=threshold,
    )
    assert _is_content_ref(r["outer"]["inner"])
    assert r["outer"]["sib"] == "short"  # small sibling untouched
    assert r["list"][0] == "tiny"
    assert _is_content_ref(r["list"][1])
    assert ts.file_create.call_count == 4  # 2 content objects x 2 files each

    # -- non-string primitives pass through unchanged --
    ts = _mock_ts()
    primitives = {"int": 42, "float": 3.14, "bool": True, "none": None}
    assert (
        replace_large_strings_with_content_objects(
            primitives, "proj", ts, min_chars=threshold
        )
        == primitives
    )
    assert ts.file_create.call_count == 0

    # -- empty structures --
    ts = _mock_ts()
    assert (
        replace_large_strings_with_content_objects({}, "p", ts, min_chars=threshold)
        == {}
    )
    assert (
        replace_large_strings_with_content_objects([], "p", ts, min_chars=threshold)
        == []
    )

    # -- multiple large strings each get their own Content object --
    ts = _mock_ts(num_files=6)
    r = replace_large_strings_with_content_objects(
        {
            "a": "a" * (threshold + 1),
            "b": "b" * (threshold + 1),
            "c": "c" * (threshold + 1),
        },
        "proj",
        ts,
        min_chars=threshold,
    )
    for k in ("a", "b", "c"):
        assert _is_content_ref(r[k])
    assert ts.file_create.call_count == 6

    # -- stored metadata is text/plain --
    ts = _mock_ts()
    replace_large_strings_with_content_objects(
        {"f": "hello " * (threshold // 6 + 1)}, "proj", ts, min_chars=threshold
    )
    meta = json.loads(ts.file_create.call_args_list[1][0][0].content)
    assert meta["mimetype"] == "text/plain"
    assert meta["content_type"] == "text"

    # -- graceful failure: broken storage returns original string --
    broken_ts = MagicMock()
    broken_ts.file_create = MagicMock(side_effect=RuntimeError("boom"))
    r = replace_large_strings_with_content_objects(
        {"f": large}, "proj", broken_ts, min_chars=threshold
    )
    assert r["f"] == large  # original preserved


def _build_minimal_wav(data_size: int) -> bytes:
    """Build a minimal valid WAV file with *data_size* bytes of silence."""
    wav = bytearray()
    wav.extend(b"RIFF")
    size_pos = len(wav)
    wav.extend(b"\x00\x00\x00\x00")  # placeholder
    wav.extend(b"WAVE")
    # fmt chunk
    wav.extend(b"fmt ")
    wav.extend((16).to_bytes(4, "little"))
    wav.extend((1).to_bytes(2, "little"))  # PCM
    wav.extend((1).to_bytes(2, "little"))  # mono
    wav.extend((44100).to_bytes(4, "little"))
    wav.extend((88200).to_bytes(4, "little"))
    wav.extend((2).to_bytes(2, "little"))
    wav.extend((16).to_bytes(2, "little"))
    # data chunk
    wav.extend(b"data")
    wav.extend(data_size.to_bytes(4, "little"))
    wav.extend(b"\x00" * data_size)
    # patch RIFF size
    wav[size_pos : size_pos + 4] = (len(wav) - 8).to_bytes(4, "little")
    return bytes(wav)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
