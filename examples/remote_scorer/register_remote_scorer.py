"""Publish a Weave RemoteScorer and activate a Monitor.

The monitor targets either a traced op (--op-name) or completed agent turns
(--agent-turn). Weave sends the op target as a V1 request and the agent-turn
target as a V2 request; see README.md.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

import weave
from weave.flow.monitor import Monitor
from weave.scorers.remote_scorer import (
    OAuthClientCredentialsConfig,
    RemoteScorer,
    StaticBearerAuthConfig,
)

AUTH_MODE_STATIC_BEARER = "static_bearer"
AUTH_MODE_OAUTH_CLIENT_CREDENTIALS = "oauth_client_credentials"
DEFAULT_OP_NAME = "sample_remote_scorer_target"
# Monitors score completed agent turns when this event name is in op_names.
AGENT_TURN_OP_NAME = "weave.genai.turn_ended"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register an externally hosted Weave remote scorer."
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Weave project, for example entity/project.",
    )
    parser.add_argument(
        "--score-url",
        required=True,
        help="Public HTTPS URL for the scorer POST endpoint.",
    )
    target = parser.add_mutually_exclusive_group()
    target.add_argument(
        "--op-name",
        default=None,
        help=(
            "Operation to monitor. Use a short op name from the same project or "
            f"a full weave:///... op ref. Default: {DEFAULT_OP_NAME}."
        ),
    )
    target.add_argument(
        "--agent-turn",
        action="store_true",
        help="Monitor completed agent turns instead of a traced op.",
    )
    parser.add_argument(
        "--scorer-name",
        default="example_remote_scorer",
        help="Name for the published RemoteScorer object.",
    )
    parser.add_argument(
        "--monitor-name",
        default="example_remote_scorer_monitor",
        help="Name for the published Monitor object.",
    )
    parser.add_argument(
        "--sampling-rate",
        type=float,
        default=1.0,
        help="Monitor sampling rate from 0.0 to 1.0.",
    )
    parser.add_argument(
        "--config-json",
        default=None,
        help="Optional JSON object surfaced to the endpoint as scorer.config.",
    )
    parser.add_argument(
        "--auth-mode",
        choices=[AUTH_MODE_STATIC_BEARER, AUTH_MODE_OAUTH_CLIENT_CREDENTIALS],
        required=True,
        help="Per-scorer auth mode to persist in Weave.",
    )
    parser.add_argument(
        "--secret-name",
        required=True,
        help=(
            "Weave/entity secret name containing the static bearer token or "
            "OAuth client secret."
        ),
    )
    parser.add_argument(
        "--token-url",
        default=None,
        help="OAuth token endpoint URL for client credentials auth.",
    )
    parser.add_argument(
        "--client-id",
        default=None,
        help="OAuth client ID for client credentials auth.",
    )
    parser.add_argument(
        "--scope",
        default=None,
        help="Optional OAuth scope.",
    )

    args = parser.parse_args()
    _validate_args(parser, args)
    return args


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    if not 0 <= args.sampling_rate <= 1:
        parser.error("--sampling-rate must be between 0.0 and 1.0")

    if args.auth_mode == AUTH_MODE_OAUTH_CLIENT_CREDENTIALS:
        missing = [
            flag
            for flag, value in [
                ("--token-url", args.token_url),
                ("--client-id", args.client_id),
            ]
            if not value
        ]
        if missing:
            parser.error(
                f"{', '.join(missing)} required for oauth_client_credentials auth"
            )


def _parse_config(raw_config: str | None) -> dict[str, Any] | None:
    if raw_config is None:
        return None
    parsed = json.loads(raw_config)
    if not isinstance(parsed, dict):
        raise TypeError("--config-json must be a JSON object")
    return parsed


def _build_auth_config(
    args: argparse.Namespace,
) -> StaticBearerAuthConfig | OAuthClientCredentialsConfig:
    if args.auth_mode == AUTH_MODE_STATIC_BEARER:
        return StaticBearerAuthConfig(
            mode=AUTH_MODE_STATIC_BEARER,
            bearer_secret_name=args.secret_name,
        )

    return OAuthClientCredentialsConfig(
        mode=AUTH_MODE_OAUTH_CLIENT_CREDENTIALS,
        token_endpoint_url=args.token_url,
        client_id=args.client_id,
        client_secret_name=args.secret_name,
        scope=args.scope,
    )


def main() -> None:
    args = parse_args()
    config = _parse_config(args.config_json)

    weave.init(args.project)
    scorer = RemoteScorer(
        name=args.scorer_name,
        endpoint_url=args.score_url,
        config=config,
        auth_config=_build_auth_config(args),
    )
    weave.publish(scorer, name=args.scorer_name)

    if args.agent_turn:
        op_name = AGENT_TURN_OP_NAME
    else:
        op_name = args.op_name or DEFAULT_OP_NAME

    monitor = Monitor(
        name=args.monitor_name,
        scorers=[scorer],
        op_names=[op_name],
        sampling_rate=args.sampling_rate,
    )
    monitor.activate()


if __name__ == "__main__":
    main()
