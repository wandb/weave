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


class TestStandaloneBase64Detection:
    """Test detection and conversion of standalone base64 strings (new functionality)."""

    def test_non_media_base64_strings_not_converted(self):
        """Test that various base64 strings of different lengths (mod 4) that decode to
        text/plain or application/octet-stream are NOT converted.
        """
        # Mock trace server
        trace_server = MagicMock()

        # Test strings of various lengths mod 4
        # These should all decode to text/plain or application/octet-stream
        test_cases = [
            # Length % 4 == 0: "aaaa" decodes to binary data
            "aaaa",
            # Length % 4 == 0: "hello" in base64
            "aGVsbG8=",
            # Length % 4 == 0: "test message"
            "dGVzdCBtZXNzYWdl",
            # Length % 4 == 0: longer text
            "VGhpcyBpcyBhIGxvbmdlciB0ZXN0IG1lc3NhZ2U=",
            # Short strings that are valid base64 but not media
            "YQ==",  # "a"
            "YWI=",  # "ab"
            "YWJj",  # "abc"
            # Random-looking base64 that's still text-like
            "SGVsbG8gV29ybGQh",  # "Hello World!"
        ]

        for test_str in test_cases:
            # First verify these match the base64 pattern
            assert is_base64(test_str), f"Expected {test_str} to match base64 pattern"

            input_data = {"field": test_str}
            result = replace_base64_with_content_objects(
                input_data, "test_project", trace_server
            )

            # These should NOT be converted because they decode to text/plain or application/octet-stream
            assert result["field"] == test_str, (
                f"Expected {test_str} to NOT be converted"
            )

        # Verify trace server was never called since nothing should be converted
        assert trace_server.file_create.call_count == 0

    def test_wav_file_base64_converted(self):
        """Test that a dict with a field containing raw base64 representing a WAV file
        is detected and converted to Content.
        """
        # Mock trace server
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest"),
                FileCreateRes(digest="metadata_digest"),
            ]
        )

        # Create a minimal valid WAV file (larger than AUTO_CONVERSION_MIN_SIZE)
        # WAV format: RIFF header + fmt chunk + data chunk
        wav_data = bytearray()

        # RIFF header
        wav_data.extend(b"RIFF")
        # Placeholder for file size (will update later)
        file_size_pos = len(wav_data)
        wav_data.extend(b"\x00\x00\x00\x00")
        wav_data.extend(b"WAVE")

        # fmt chunk
        wav_data.extend(b"fmt ")
        wav_data.extend((16).to_bytes(4, "little"))  # chunk size
        wav_data.extend((1).to_bytes(2, "little"))  # audio format (PCM)
        wav_data.extend((1).to_bytes(2, "little"))  # num channels
        wav_data.extend((44100).to_bytes(4, "little"))  # sample rate
        wav_data.extend((88200).to_bytes(4, "little"))  # byte rate
        wav_data.extend((2).to_bytes(2, "little"))  # block align
        wav_data.extend((16).to_bytes(2, "little"))  # bits per sample

        # data chunk - make it large enough to exceed AUTO_CONVERSION_MIN_SIZE
        audio_data_size = LARGE_TEST_DATA_SIZE
        wav_data.extend(b"data")
        wav_data.extend(audio_data_size.to_bytes(4, "little"))
        # Add audio data (silence)
        wav_data.extend(b"\x00" * audio_data_size)

        # Update file size in RIFF header (total size - 8 bytes for RIFF header)
        file_size = len(wav_data) - 8
        wav_data[file_size_pos : file_size_pos + 4] = file_size.to_bytes(4, "little")

        # Encode as base64
        wav_base64 = base64.b64encode(bytes(wav_data)).decode("ascii")

        # Verify it matches base64 pattern
        assert is_base64(wav_base64)

        # Test that it gets converted
        input_data = {
            "audio_field": wav_base64,
            "other_field": "normal string",
        }

        result = replace_base64_with_content_objects(
            input_data, "test_project", trace_server
        )

        # The WAV file should be converted to Content object
        assert isinstance(result["audio_field"], dict)
        assert result["audio_field"]["_type"] == "CustomWeaveType"
        assert (
            result["audio_field"]["weave_type"]["type"]
            == "weave.type_wrappers.Content.content.Content"
        )
        assert "files" in result["audio_field"]
        assert "content" in result["audio_field"]["files"]
        assert "metadata.json" in result["audio_field"]["files"]

        # Normal string should be unchanged
        assert result["other_field"] == "normal string"

        # Verify file_create was called twice (content + metadata)
        assert trace_server.file_create.call_count == 2

        # Detected audio/x-wav is normalized to canonical audio/wav.
        metadata_call = trace_server.file_create.call_args_list[1][0][0]
        metadata = json.loads(metadata_call.content)
        assert metadata["mimetype"] == "audio/wav"


class TestThresholdAndStructuralIdentity:
    """Pins the auto-conversion threshold and the "don't copy unchanged subtrees" behaviour.

    These exist because both knobs are part of the hot path on every
    ``upsert_batch``: the threshold gates how much expensive regex / decode
    work runs on long-but-not-binary strings, and the in-place return path
    avoids allocating a fresh dict/list on each level of a no-binary payload.
    """

    def test_auto_conversion_threshold_is_eight_kib(self):
        """Regression guard: the threshold has a real cost when lowered."""
        # If someone drops this back to 1024, all the mid-sized LLM outputs in
        # production traces start hitting `is_data_uri` + `is_base64` again —
        # the very work the threshold bump was meant to skip.
        assert AUTO_CONVERSION_MIN_SIZE == 8192

    def test_string_below_threshold_does_not_invoke_storage(self):
        """A 1-8 KiB string must short-circuit on size; no regex, no storage."""
        trace_server = MagicMock()
        # 4 KiB string of valid-looking base64 alphabet — would have decoded
        # successfully under the old threshold and gone through the regex
        # path. Now it must be returned untouched.
        below_threshold = "A" * 4096
        result = replace_base64_with_content_objects(
            {"field": below_threshold}, "test_project", trace_server
        )
        assert result["field"] == below_threshold
        assert trace_server.file_create.call_count == 0

    def test_no_replacement_returns_same_object_identity(self):
        """If nothing changed, the caller gets back the original dict object.

        This is what makes the no-binary hot path cheap: every level whose
        children are all untouched returns the same reference instead of
        allocating a fresh copy. Identity matters here — checking equality
        wouldn't catch a regression to the always-allocate code path.
        """
        trace_server = MagicMock()
        original = {
            "messages": [
                {"role": "user", "content": "no binary here"},
                {"role": "assistant", "content": "still nothing"},
            ],
            "metadata": {"trace_id": "abc"},
        }
        result = replace_base64_with_content_objects(
            original, "test_project", trace_server
        )
        # The outer dict, the messages list, every inner message dict, and
        # the metadata dict must all be the same object as the input — no
        # copies anywhere on a clean no-binary tree.
        assert result is original
        assert result["messages"] is original["messages"]
        assert result["messages"][0] is original["messages"][0]
        assert result["metadata"] is original["metadata"]

    def test_partial_replacement_copies_only_affected_subtrees(self):
        """A replacement on one branch must not allocate copies on the others."""
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest"),
                FileCreateRes(digest="metadata_digest"),
            ]
        )
        png_data_uri = "data:image/png;base64," + base64.b64encode(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 12000
        ).decode("ascii")

        untouched_branch = {"role": "assistant", "content": "plain reply"}
        touched_branch = {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": png_data_uri}}],
        }
        original = {
            "messages": [untouched_branch, touched_branch],
            "model": "claude-sonnet-4-6",
        }

        result = replace_base64_with_content_objects(
            original, "test_project", trace_server
        )

        # Branches with no replacement keep their identity.
        assert result["messages"][0] is untouched_branch
        # The branch that did get a replacement is a fresh object whose
        # rewritten subtree no longer matches the source.
        assert result["messages"][1] is not touched_branch
        # And critically: the input dict was not mutated.
        assert touched_branch["content"][0]["image_url"]["url"] == png_data_uri

    def test_partial_replacement_in_list_isolates_unchanged_indices(self):
        """List sibling of the dict-partial test: only the touched index is copied.

        Without this the list branch of ``_visit_children`` is only exercised
        in the all-changed and all-unchanged extremes, which leaves the
        "first-change triggers a copy of the whole list" path partially
        covered (codecov flagged this on the original PR).
        """
        trace_server = MagicMock()
        trace_server.file_create = MagicMock(
            side_effect=[
                FileCreateRes(digest="content_digest"),
                FileCreateRes(digest="metadata_digest"),
            ]
        )
        png_data_uri = "data:image/png;base64," + base64.b64encode(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 12000
        ).decode("ascii")

        untouched_message = {"role": "user", "content": "plain text"}
        touched_message = {"role": "assistant", "content": png_data_uri}
        other_untouched_message = {"role": "tool", "content": "also plain"}
        original_messages = [
            untouched_message,
            touched_message,
            other_untouched_message,
        ]
        original = {"messages": original_messages, "model": "claude-sonnet-4-6"}

        result = replace_base64_with_content_objects(
            original, "test_project", trace_server
        )

        # The list itself was copied (one of its entries changed), but the
        # unchanged dict entries keep their identity inside the new list.
        assert result["messages"] is not original_messages
        assert result["messages"][0] is untouched_message
        assert result["messages"][2] is other_untouched_message
        # The touched entry was replaced — different identity, and the
        # original dict is left intact.
        assert result["messages"][1] is not touched_message
        assert touched_message["content"] == png_data_uri

    def test_caller_overwrite_safe_after_in_place_return(self):
        """Caller pattern ``req.start.inputs = replace_base64(...)`` is safe.

        Confirms the no-copy path doesn't introduce a subtle aliasing bug:
        even though the result is the same object as the input, the
        ``CallStartReq`` machinery in ``process_call_req_to_content`` just
        rebinds the field, which is fine.
        """
        from datetime import datetime, timezone

        trace_server = MagicMock()
        inputs_before = {"text": "no binary content here"}
        start_req = CallStartReq(
            start=StartedCallSchemaForInsert(
                project_id="proj",
                op_name="op",
                started_at=datetime.now(timezone.utc),
                attributes={},
                inputs=inputs_before,
            )
        )
        processed = process_call_req_to_content(start_req, trace_server)
        # Pydantic shallow-copies inputs at model construction, so we compare
        # by value rather than identity here — content must round-trip
        # unchanged regardless of the SDK copy.
        assert processed.start.inputs == inputs_before
        assert trace_server.file_create.call_count == 0


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
