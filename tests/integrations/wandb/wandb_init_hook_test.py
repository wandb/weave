"""Tests for the wandb init hook behavior."""

from __future__ import annotations

import importlib
import sys
import types
from dataclasses import dataclass

import pytest


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
        wandb_mod = types.SimpleNamespace(integration=integration_mod)

        for name, mod in [
            ("wandb", wandb_mod),
            ("wandb.integration", integration_mod),
            ("wandb.integration.weave", weave_mod),
        ]:
            monkeypatch.setitem(sys.modules, name, mod)

        # Patch weave.integrations.wandb.wandb.init to record calls
        target_module = importlib.import_module("weave.integrations.wandb.wandb")
        calls = []

        def fake_init(project_name=None, **_):
            calls.append(project_name)

        monkeypatch.setattr(target_module, "init", fake_init, raising=True)
        return calls

    return _install


@dataclass
class TestCase:
    name: str
    active_run: RunPath | None
    expected_calls: list[str]


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
        # TODO: What if there are multiple active runs?
    ],
    ids=lambda tc: tc.name,
)
def test_wandb_init_hook_behavior(tc, install_fake_wandb):
    calls = install_fake_wandb(tc.active_run)
    wandb_integration_module = importlib.import_module("weave.integrations.wandb.wandb")
    wandb_integration_module.wandb_init_hook()
    assert calls == tc.expected_calls
