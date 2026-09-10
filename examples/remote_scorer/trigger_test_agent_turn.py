"""Log one completed agent turn that can trigger a remote scorer monitor."""

from __future__ import annotations

import argparse
import uuid

from opentelemetry import trace

import weave
from weave.conversation import Message, log_turn

DEFAULT_AGENT_NAME = "sample-support-agent"
DEFAULT_SYSTEM_INSTRUCTION = "Answer the user accurately and concisely."
DEFAULT_INPUT_TEXT = "How do I reset my password?"
DEFAULT_OUTPUT_TEXT = "Open Settings, choose Security, then select Reset password."

FLUSH_TIMEOUT_MILLISECONDS = 30_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a sample agent turn for remote scorer smoke testing."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Weave project, for example entity/project.",
    )
    parser.add_argument(
        "--agent-name",
        default=DEFAULT_AGENT_NAME,
        help="Agent name recorded on the turn.",
    )
    parser.add_argument(
        "--conversation-id",
        default=None,
        help="Conversation the turn belongs to. Default: a new random id.",
    )
    parser.add_argument(
        "--input",
        default=DEFAULT_INPUT_TEXT,
        dest="input_text",
        help="User message for the turn.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_TEXT,
        dest="output_text",
        help="Assistant message for the turn.",
    )
    return parser.parse_args()


def flush_logged_turn() -> None:
    """Wait for the turn to reach Weave before the process exits.

    weave.init installs an OpenTelemetry provider that exports spans from a
    background thread. Without a flush, a short script can exit first.
    """
    force_flush = getattr(trace.get_tracer_provider(), "force_flush", None)
    if force_flush is None:
        raise RuntimeError(
            "weave.init registered no span exporter, so the turn was not sent."
        )
    force_flush(FLUSH_TIMEOUT_MILLISECONDS)


def main() -> None:
    args = parse_args()
    weave.init(args.project)

    result = log_turn(
        conversation_id=args.conversation_id or f"sample-{uuid.uuid4().hex}",
        agent_name=args.agent_name,
        system_instructions=[DEFAULT_SYSTEM_INSTRUCTION],
        messages=[Message.user(args.input_text)],
        output_messages=[Message.assistant(args.output_text)],
    )
    flush_logged_turn()

    print("Created sample agent turn.")
    print(f"Conversation: {result.conversation_id}")
    print(f"Trace IDs: {result.trace_ids}")
    print("Monitor scoring is asynchronous; check Weave feedback and scorer logs.")


if __name__ == "__main__":
    main()
