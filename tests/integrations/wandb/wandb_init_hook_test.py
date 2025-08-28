"""Tests for the wandb init hook behavior."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass

import pytest

import weave.integrations.wandb.wandb


@dataclass
class RunPath:
    entity: str
    project: str


@pytest.fixture
def install_fake_wandb(monkeypatch):
    def _install(active_run_return: RunPath | None):
        # Minimal fake wandb module structure
        weave_mod = types.SimpleNamespace(active_run_path=lambda: active_run_return)
        integration_mod = types.SimpleNamespace(weave=weave_mod)
        wandb_mod = types.SimpleNamespace(integration=integration_mod, run=None)

        for name, mod in [
            ("wandb", wandb_mod),
            ("wandb.integration", integration_mod),
            ("wandb.integration.weave", weave_mod),
        ]:
            monkeypatch.setitem(sys.modules, name, mod)

        # Patch weave.integrations.wandb.wandb.init to record calls
        calls = []

        def fake_init(project_name=None):
            calls.append(project_name)

        monkeypatch.setattr(weave.integrations.wandb.wandb, "init", fake_init)
        return calls

    return _install


@dataclass
class TestCase:
    name: str
    active_run: RunPath | None
    expected_calls: list[str]
    env_vars: dict[str, str] | None = None


@pytest.mark.parametrize(
    "tc",
    [
        TestCase(
            name="no_active_run",
            active_run=None,
            expected_calls=[],
        ),
        TestCase(
            name="active_run",
            active_run=RunPath(entity="ent", project="proj"),
            expected_calls=["ent/proj"],
        ),
        TestCase(
            name="active_run_with_weave_disabled",
            active_run=RunPath(entity="ent", project="proj"),
            expected_calls=[],
            env_vars={"WANDB_DISABLE_WEAVE": "true"},
        ),
        # TODO: What if there are multiple active runs?
    ],
    ids=lambda tc: tc.name,
)
def test_wandb_init_hook_behavior(tc, install_fake_wandb, monkeypatch):
    # Set environment variables if specified
    if tc.env_vars:
        for key, value in tc.env_vars.items():
            monkeypatch.setenv(key, value)

    calls = install_fake_wandb(tc.active_run)
    weave.integrations.wandb.wandb.wandb_init_hook()

    assert calls == tc.expected_calls
