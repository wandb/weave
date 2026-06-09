"""Create a traced call that can trigger a remote scorer monitor."""

from __future__ import annotations

import argparse

import weave

DEFAULT_OP_NAME = "sample_remote_scorer_target"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Send a sample traced call for remote scorer smoke testing."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Weave project, for example entity/project.",
    )
    parser.add_argument(
        "--op-name",
        default=DEFAULT_OP_NAME,
        help="Traced op name. Use the same value passed to register_remote_scorer.py.",
    )
    parser.add_argument(
        "--message",
        default="test message for scoring",
        help="Message to send through the traced operation.",
    )
    return parser.parse_args()


def make_sample_op(op_name: str):
    @weave.op(name=op_name)
    def sample_remote_scorer_target(message: str) -> dict[str, str]:
        return {
            "reply": f"received: {message}",
            "status": "ok",
        }

    return sample_remote_scorer_target


def main() -> None:
    args = parse_args()
    weave.init(args.project)

    sample_op = make_sample_op(args.op_name)
    output = sample_op(args.message)

    print("Created sample traced call.")
    print(f"Operation: {args.op_name}")
    print(f"Output: {output}")
    print("Monitor scoring is asynchronous; check Weave feedback and scorer logs.")


if __name__ == "__main__":
    main()
