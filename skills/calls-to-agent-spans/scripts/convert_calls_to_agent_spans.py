"""Convert a Weave project's classic calls into agent spans.

Reads `/calls/stream_query` and writes OTLP to `/agents/otel/v1/traces`, so it needs nothing but an
API key. Run `--dry-run` first: it prints the mapping, coverage, and sample spans, without writing.
"""

from __future__ import annotations

import argparse
import json
import os

import requests
from calls_client import (
    BASE_COLUMNS,
    DEFAULT_BASE_URL,
    DETECTION_SAMPLE,
    attach_tool_payloads,
    fetch_calls,
    span_count,
)
from otlp_export import EXPORT_BATCH, export_spans, to_otlp
from payload_paths import infer_mapping, select_columns
from span_builder import build_spans, op_short, turn_texts


def convert(
    session: requests.Session, base_url: str, args: argparse.Namespace
) -> dict[str, object]:
    """Read the window, map it to spans, and export unless this is a dry run."""
    if args.source_project == args.target_project:
        raise SystemExit("refusing to write to the source project")
    window = (args.started_after, args.started_before)
    sample = fetch_calls(
        session,
        base_url,
        args.source_project,
        *window,
        None,
        roots_only=True,
        max_rows=DETECTION_SAMPLE,
    )
    mapping = infer_mapping(
        sample,
        {
            "conversation": args.conversation_path,
            "user": args.user_path,
            "assistant": args.assistant_path,
        },
    )
    columns = select_columns(
        BASE_COLUMNS + [path for paths in mapping.values() for path in paths]
    )
    calls = fetch_calls(session, base_url, args.source_project, *window, columns)
    attach_tool_payloads(session, base_url, args.source_project, window, calls)
    spans = build_spans(calls, mapping)
    report: dict[str, object] = {
        "mapping": mapping,
        "calls": len(calls),
        "spans": len(spans),
        "coverage": _coverage(calls, mapping, spans),
    }
    if args.dry_run:
        report["sample_spans"] = [
            {
                "name": span["name"],
                "kind": span["kind"],
                "attributes": span["attributes"],
            }
            for span in spans[:3]
        ]
        return report
    if not args.allow_existing and span_count(session, base_url, args.target_project):
        raise SystemExit(
            "target already has agent spans; pass --allow-existing for a disjoint window"
        )
    for start in range(0, len(spans), EXPORT_BATCH):
        export_spans(
            session,
            base_url,
            args.target_project,
            to_otlp(spans[start : start + EXPORT_BATCH]),
        )
    return {**report, "exported": len(spans)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-project", required=True, metavar="ENTITY/PROJECT")
    parser.add_argument("--target-project", required=True, metavar="ENTITY/PROJECT")
    parser.add_argument("--started-after", required=True, metavar="ISO8601")
    parser.add_argument("--started-before", default="", metavar="ISO8601")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--conversation-path", default="")
    parser.add_argument("--user-path", default="")
    parser.add_argument("--assistant-path", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-existing", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("WANDB_API_KEY", "")
    if not api_key:
        raise SystemExit("set WANDB_API_KEY")
    session = requests.Session()
    session.auth = ("api", api_key)
    print(json.dumps(convert(session, args.base_url.rstrip("/"), args), indent=2))


def _coverage(
    calls: list[dict[str, object]],
    mapping: dict[str, list[str]],
    spans: list[dict[str, object]],
) -> dict[str, object]:
    """Root ops whose turn text is still empty, plus spans that got no operation."""
    by_trace: dict[str, list[dict[str, object]]] = {}
    for call in calls:
        by_trace.setdefault(str(call.get("trace_id") or ""), []).append(call)
    missing_user: list[str] = []
    missing_assistant: list[str] = []
    for trace_calls in by_trace.values():
        root = next((call for call in trace_calls if not call.get("parent_id")), None)
        if root is None:
            continue
        user, assistant = turn_texts(root, trace_calls, mapping)
        name = op_short(root)
        if not user:
            missing_user.append(name)
        if not assistant:
            missing_assistant.append(name)
    unlabeled = [
        str(span["name"])
        for span in spans
        if not (span["attributes"] or {}).get("weave.operation.name")
    ]
    return {
        "missing_user": missing_user,
        "missing_assistant": missing_assistant,
        "unlabeled": unlabeled,
    }


if __name__ == "__main__":
    main()
