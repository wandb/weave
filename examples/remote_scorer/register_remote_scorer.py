"""Publish a Weave RemoteScorer and activate a Monitor."""

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
    parser.add_argument(
        "--op-name",
        default=DEFAULT_OP_NAME,
        help=(
            "Operation to monitor. Use a short op name from the same project or "
            "a full weave:///... op ref."
        ),
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
        raise ValueError("--config-json must be a JSON object")
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

    monitor = Monitor(
        name=args.monitor_name,
        scorers=[scorer],
        op_names=[args.op_name],
        sampling_rate=args.sampling_rate,
    )
    monitor.activate()


if __name__ == "__main__":
    main()
