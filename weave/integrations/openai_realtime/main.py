from __future__ import annotations

import argparse
import json
from pathlib import Path

from conversation_manager import ConversationManager
from exporters import DirectoryExportAdapter, JSONFileExportAdapter
from weave.integrations.openai_realtime.models import (
    USER_MESSAGE_CLASSES,
    SERVER_MESSAGE_CLASSES,
    UnknownClientMessage,
    create_message_from_dict
)


def _parse_message(data: dict):
    et = data.get("type") or ""
    if et in USER_MESSAGE_CLASSES:
        return USER_MESSAGE_CLASSES[et](**data)
    if et in SERVER_MESSAGE_CLASSES:
        return SERVER_MESSAGE_CLASSES[et](**data)
    # default to client unknown
    return UnknownClientMessage(**data)


def cmd_replay_jsonl(args: argparse.Namespace) -> int:
    mgr = ConversationManager()

    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")

    # Replay JSONL
    for line in in_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        print(rec)
        msg = create_message_from_dict(rec)
        mgr.process_event(msg)

    # Export
    if args.export == "json":
        JSONFileExportAdapter().export(mgr, args.out)
    elif args.export == "dir":
        DirectoryExportAdapter(audio_format=args.audio_format).export(mgr, args.out)
    else:
        # No export, print quick summary directly from state
        print(f"Items: {len(mgr.state.items)}, Responses: {len(mgr.state.responses)}")
    return 0


def cmd_replay_turns(args: argparse.Namespace) -> int:
    mgr = ConversationManager()
    out_dir = args.out
    mgr.turn_export_dir = out_dir

    in_path = Path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")

    # Replay JSONL
    for line in in_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        data = rec.get("data") or rec
        msg = _parse_message(data)
        mgr.process_event(msg)

    # Give any debounce timers a moment to flush
    import time as _t
    _t.sleep(0.25)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Conversation Manager CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    rp = sub.add_parser("replay", help="Replay a JSONL event file and optionally export state")
    rp.add_argument("input", help="Path to JSONL file with events")
    rp.add_argument("--export", choices=["none", "json", "dir"], default="none")
    rp.add_argument("--out", help="Output path (file or dir depending on export)", default="state.json")
    rp.add_argument("--audio-format", choices=["pcm", "wav"], default="pcm", help="Audio file format for dir export")
    rp.set_defaults(func=cmd_replay_jsonl)

    rtp = sub.add_parser("replay-turns", help="Replay a JSONL event file and export conversation turns")
    rtp.add_argument("input", help="Path to JSONL file with events")
    rtp.add_argument("--out", help="Output directory for turn files", default="turns")
    rtp.set_defaults(func=cmd_replay_turns)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
