"""Convert a Weave project's classic calls into agent spans.

Reads `/calls/stream_query` and writes OTLP to `/agents/otel/v1/traces`, so it needs nothing but an
API key. Run `--dry-run` first: it prints the mapping it inferred and the spans it would send,
without writing anything.
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
)
from otlp_export import EXPORT_BATCH, export_spans, to_otlp
from payload_paths import infer_mapping, select_columns
from span_builder import build_spans


def convert(
    session: requests.Session, base_url: str, args: argparse.Namespace
) -> dict[str, object]:
    """Read the window, map it to spans, and export unless this is a dry run."""
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
    args = parser.parse_args()

    api_key = os.environ.get("WANDB_API_KEY", "")
    if not api_key:
        raise SystemExit("set WANDB_API_KEY")
    session = requests.Session()
    session.auth = ("api", api_key)
    print(json.dumps(convert(session, args.base_url.rstrip("/"), args), indent=2))


if __name__ == "__main__":
    main()
