"""Tests that `weave.telemetry.trace_sentry.Sentry` honors `WANDB_ERROR_REPORTING`.

The wandb SDK's own Sentry wrapper (`wandb/analytics/sentry.py`) reads
`WANDB_ERROR_REPORTING` to let customers in security-sensitive environments
disable outbound error reporting. The Weave SDK's parallel wrapper must
behave the same way so that a single env var disables both.

Truthy / falsy semantics match the canonical `_parse_bool` helper in
`weave/trace/settings.py` (i.e. only `yes`, `true`, `1`, `on` keep reporting
enabled; everything else, including unrecognized values, disables it).
"""

from __future__ import annotations

import pytest

from weave.telemetry import trace_sentry

# `None` means leave `WANDB_ERROR_REPORTING` unset entirely.
_UNSET = None


@pytest.mark.parametrize(
    ("value", "disabled"),
    [
        # Not-truthy values disable Sentry outright.
        ("false", True),
        ("False", True),
        ("FALSE", True),
        ("0", True),
        ("no", True),
        ("off", True),
        ("anything-else", True),
        ("", True),
        # Truthy values and an unset var keep reporting enabled (modulo the
        # optional `sentry-sdk` dependency reflected by `SENTRY_AVAILABLE`).
        ("true", not trace_sentry.SENTRY_AVAILABLE),
        ("True", not trace_sentry.SENTRY_AVAILABLE),
        ("TRUE", not trace_sentry.SENTRY_AVAILABLE),
        ("1", not trace_sentry.SENTRY_AVAILABLE),
        ("yes", not trace_sentry.SENTRY_AVAILABLE),
        ("Yes", not trace_sentry.SENTRY_AVAILABLE),
        ("on", not trace_sentry.SENTRY_AVAILABLE),
        ("ON", not trace_sentry.SENTRY_AVAILABLE),
        (_UNSET, not trace_sentry.SENTRY_AVAILABLE),
    ],
)
def test_wandb_error_reporting_controls_disabled(
    monkeypatch: pytest.MonkeyPatch, value: str | None, disabled: bool
) -> None:
    """`WANDB_ERROR_REPORTING` truthiness (and absence) drives `Sentry._disabled`."""
    if value is _UNSET:
        monkeypatch.delenv("WANDB_ERROR_REPORTING", raising=False)
    else:
        monkeypatch.setenv("WANDB_ERROR_REPORTING", value)
    sentry = trace_sentry.Sentry()
    assert sentry._disabled is disabled


def test_setup_is_a_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """When disabled, `setup()` does not create a Sentry client and `scope` stays None.

    This is the load-bearing assertion for WB-34041: no Sentry client means no
    transport thread, which means no outbound traffic to the hardcoded DSN.
    """
    monkeypatch.setenv("WANDB_ERROR_REPORTING", "false")
    sentry = trace_sentry.Sentry()
    sentry.setup()
    assert sentry.scope is None
