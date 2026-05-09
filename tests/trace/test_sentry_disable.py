"""Tests that `weave.telemetry.trace_sentry.Sentry` honors `WANDB_ERROR_REPORTING`.

The wandb SDK's own Sentry wrapper (`wandb/analytics/sentry.py`) reads
`WANDB_ERROR_REPORTING` to let customers in security-sensitive environments
disable outbound error reporting. The Weave SDK's parallel wrapper must
behave the same way so that a single env var disables both.
"""

from __future__ import annotations

import pytest

from weave.telemetry import trace_sentry


@pytest.mark.parametrize(
    "value",
    ["false", "False", "FALSE", "0", "no", "No", "off", "OFF", "f", "n"],
)
def test_disabled_when_wandb_error_reporting_falsy(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Falsy spellings of `WANDB_ERROR_REPORTING` disable Sentry."""
    monkeypatch.setenv("WANDB_ERROR_REPORTING", value)
    sentry = trace_sentry.Sentry()
    assert sentry._disabled is True


@pytest.mark.parametrize(
    "value",
    ["true", "True", "TRUE", "1", "yes", "on", "anything-else", ""],
)
def test_enabled_unless_wandb_error_reporting_is_falsy(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Anything other than a recognized falsy value leaves Sentry enabled.

    `_disabled` still reflects `SENTRY_AVAILABLE` so this passes whether or
    not the optional `sentry-sdk` dependency is installed in the env.
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


def test_value_is_stripped_and_case_insensitive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Whitespace and casing in the env value should not change the outcome."""
    monkeypatch.setenv("WANDB_ERROR_REPORTING", "  False  ")
    sentry = trace_sentry.Sentry()
    assert sentry._disabled is True
