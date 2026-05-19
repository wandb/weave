"""CPU microbench for ``replace_base64_with_content_objects``.

Background: DD trace ``6a0c7d9900000000975ce4fb10f7c246`` shows a single
454ms leaf span on ``process_complete_call_to_content`` with no children,
while the other 49 calls in the same batch averaged ~5ms. The hot path is
in ``weave/trace_server/base64_content_conversion.py``: large
non-base64 strings (e.g. ``"x" * 500``) pass the regex pattern, run
through ``Content.from_base64`` (b64decode validate=True + sha256 +
libmagic mimetype probe), and only get rejected at the mimetype check.

This bench measures the three payload shapes that matter on prod ingest:
  pathological   a 50KB dict with one field of ``"x" * 500``. Worst case
                 today: the regex matches, b64decode succeeds, libmagic
                 returns ``application/octet-stream``, all work is thrown
                 away. Goal: kill this with an O(1) entropy guard.
  chat_history   a 50KB nested chat-history payload (no base64). Stresses
                 the recursion / per-string membership checks on the
                 happy path that production traces actually look like.
  data_uri       a real 1x1 PNG wrapped in a ``data:image/png;base64,...``
                 URI. Anti-regression: real binary blobs must still hit
                 ``store_content_object``.

Run twice (once on master, once on the branch), diff the medians.
"""

from __future__ import annotations

import base64
import gc
import statistics
import time
import tracemalloc
from typing import Any
from unittest.mock import MagicMock

from weave.trace_server.base64_content_conversion import (
    replace_base64_with_content_objects,
)
from weave.trace_server.trace_server_interface import FileCreateRes

ITERATIONS = 1000
PATHOLOGICAL_BAIT = "x" * 500

# Smallest real 1x1 transparent PNG, base64-encoded. Used both for the
# ``data:`` URI case and to validate real-base64 detection didn't regress.
_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


def _build_pathological() -> dict[str, Any]:
    """50KB dict whose only "interesting" field is the bait string.

    The bait is a long run of a single character: it satisfies the
    ``[A-Za-z0-9+/]+={0,2}`` pattern, so on master it flows into
    ``Content.from_base64`` (b64decode validate=True + sha256 + libmagic
    mimetype probe) before getting rejected on a ``application/octet-stream``
    mimetype. The fix short-circuits this with an O(1) entropy guard.

    Size is tuned so the payload itself is ~50KB and the bait alone clears
    ``AUTO_CONVERSION_MIN_SIZE`` (8 KiB) by a wide margin so the regex path
    is genuinely entered on master.
    """
    bait = "x" * 50000
    return {"bait": bait}


def _build_chat_history() -> dict[str, Any]:
    """Nested chat-history payload, ~50KB, zero base64 anywhere.

    Models the common shape of LLM trace inputs/outputs so the bench
    captures the per-string overhead of ``len(val) > AUTO_CONVERSION_MIN_SIZE``
    plus regex work and the recursive walk.
    """
    long_text = (
        "The quick brown fox jumps over the lazy dog. " * 200
    )  # ~9KB of natural text
    return {
        "model": "claude-sonnet-4-6",
        "messages": [
            {"role": "user", "content": "Explain transformers in detail."},
            {"role": "assistant", "content": long_text},
            {"role": "user", "content": "Now add a code example."},
            {"role": "assistant", "content": long_text},
            {"role": "user", "content": "Cool, summarize it."},
            {"role": "assistant", "content": long_text},
        ],
        "metadata": {"trace_id": "abc", "tags": ["bench", "chat"]},
    }


def _build_data_uri_payload() -> dict[str, Any]:
    """Real PNG data-URI inside a chat-shaped payload.

    Used to confirm the data-URI path still triggers `store_content_object`
    after the optimization, and to measure its cost end-to-end.
    """
    # Pad the PNG to clear AUTO_CONVERSION_MIN_SIZE (encoded > 8 KiB).
    padded = _PNG_BYTES + b"\x00" * 7000
    b64 = base64.b64encode(padded).decode("ascii")
    return {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    }
                ],
            }
        ]
    }


def _make_trace_server() -> MagicMock:
    trace_server = MagicMock()
    trace_server.file_create = MagicMock(
        side_effect=lambda req: FileCreateRes(digest=f"digest_{req.name}")
    )
    return trace_server


def _bench(payload_factory: Any, label: str) -> dict[str, float]:
    """Time ``replace_base64_with_content_objects`` over ITERATIONS calls.

    Returns median, p95, mean in nanoseconds.
    """
    trace_server = _make_trace_server()
    # Build the payload once and reuse it: we are timing the conversion walk,
    # not payload allocation. (The data-URI walk does call ``file_create``,
    # so the MagicMock side-effect is configured to keep returning fresh
    # digests indefinitely.)
    payload = payload_factory()
    samples: list[int] = []
    gc.collect()
    gc.disable()
    try:
        for _ in range(ITERATIONS):
            t0 = time.perf_counter_ns()
            replace_base64_with_content_objects(payload, "p", trace_server)
            samples.append(time.perf_counter_ns() - t0)
    finally:
        gc.enable()
    samples.sort()
    return {
        "label": label,
        "median_ns": float(samples[len(samples) // 2]),
        "p95_ns": float(samples[int(len(samples) * 0.95)]),
        "mean_ns": statistics.fmean(samples),
        "min_ns": float(samples[0]),
    }


def _peak_memory(payload_factory: Any) -> int:
    """Tracemalloc peak bytes for one full ITERATIONS run of the bench."""
    trace_server = _make_trace_server()
    payload = payload_factory()
    gc.collect()
    tracemalloc.start()
    for _ in range(ITERATIONS):
        replace_base64_with_content_objects(payload, "p", trace_server)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak


def main() -> None:
    cases = [
        ("pathological", _build_pathological),
        ("chat_history", _build_chat_history),
        ("data_uri", _build_data_uri_payload),
    ]

    print("# base64 conversion microbench")
    print(f"iterations={ITERATIONS}")
    print()
    print("| case | median (ns) | p95 (ns) | mean (ns) | min (ns) |")
    print("|---|---|---|---|---|")
    results: dict[str, dict[str, float]] = {}
    for label, factory in cases:
        r = _bench(factory, label)
        results[label] = r
        print(
            f"| {label} | {r['median_ns']:.0f} | {r['p95_ns']:.0f} |"
            f" {r['mean_ns']:.0f} | {r['min_ns']:.0f} |"
        )

    print()
    peak = _peak_memory(_build_pathological)
    print(f"pathological tracemalloc peak bytes: {peak}")


if __name__ == "__main__":
    main()
