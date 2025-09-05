from __future__ import annotations

import argparse
import json
from pathlib import Path
import weave
import dotenv
dotenv.load_dotenv()

weave.init("test_realtime_2")

from conversation_manager import ConversationManager
from weave.integrations.openai_realtime.models import (
    create_message_from_dict
)



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
        try:
            msg = create_message_from_dict(rec)
        except Exception as e:
            raise ValueError(f"create_message_from_dict for value: {rec} failed with error - {e}\n ") 
        mgr.process_event(msg)

    return 0


def cmd_replay_turns(args: argparse.Namespace) -> int:
    mgr = ConversationManager()
    out_dir = args.out

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
