"""Tests that `weave.telemetry.trace_sentry.Sentry` honors `WANDB_ERROR_REPORTING`.

The wandb SDK's own Sentry wrapper (`wandb/analytics/sentry.py`) reads
`WANDB_ERROR_REPORTING` to let customers in security-sensitive environments
disable outbound error reporting. The Weave SDK's parallel wrapper must
behave the same way so that a single env var disables both.

Truthy / falsy semantics match the canonical `_str2bool_truthy` helper in
`weave/trace/settings.py` (i.e. only `yes`, `true`, `1`, `on` keep reporting
enabled; everything else, including unrecognized values, disables it).
"""

from __future__ import annotations

import pytest

from weave.telemetry import trace_sentry


@pytest.mark.parametrize(
    "value",
    ["false", "False", "FALSE", "0", "no", "off", "anything-else", ""],
)
def test_disabled_when_wandb_error_reporting_is_not_truthy(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Anything that is not a recognized truthy value disables Sentry."""
    monkeypatch.setenv("WANDB_ERROR_REPORTING", value)
    sentry = trace_sentry.Sentry()
    assert sentry._disabled is True


@pytest.mark.parametrize(
    "value",
    ["true", "True", "TRUE", "1", "yes", "Yes", "on", "ON"],
)
def test_enabled_when_wandb_error_reporting_is_truthy(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Recognized truthy values leave Sentry enabled (modulo `SENTRY_AVAILABLE`).

    `_disabled` still reflects whether the optional `sentry-sdk` dependency is
    installed in the env, so this passes whether or not Sentry is importable.
    """
    monkeypatch.setenv("WANDB_ERROR_REPORTING", value)
    sentry = trace_sentry.Sentry()
    assert sentry._disabled == (not trace_sentry.SENTRY_AVAILABLE)


def test_enabled_when_wandb_error_reporting_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unset `WANDB_ERROR_REPORTING` defaults to enabled (no opt-out)."""
    monkeypatch.delenv("WANDB_ERROR_REPORTING", raising=False)
    sentry = trace_sentry.Sentry()
    assert sentry._disabled == (not trace_sentry.SENTRY_AVAILABLE)


def test_setup_is_a_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """When disabled, `setup()` does not create a Sentry client and `scope` stays None.

    This is the load-bearing assertion for WB-34041: no Sentry client means no
    transport thread, which means no outbound traffic to the hardcoded DSN.
    """
    monkeypatch.setenv("WANDB_ERROR_REPORTING", "false")
    sentry = trace_sentry.Sentry()
    sentry.setup()
    assert sentry.scope is None
