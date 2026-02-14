from pathlib import Path

import pytest

from weave.trace import env as trace_env


def _write_netrc(path: Path, machine: str, password: str) -> None:
    path.write_text(
        f"machine {machine}\n  login user\n  password {password}\n",
        encoding="utf-8",
    )


def test_wandb_api_key_via_netrc_file_returns_none_for_missing_file(tmp_path):
    netrc_path = tmp_path / ".netrc"

    assert trace_env._wandb_api_key_via_netrc_file(str(netrc_path)) is None


def test_wandb_api_key_via_netrc_file_reads_key_for_matching_host(
    tmp_path, monkeypatch
):
    netrc_path = tmp_path / ".netrc"
    _write_netrc(netrc_path, "api.wandb.ai", "netrc-key")
    monkeypatch.setattr(trace_env, "wandb_base_url", lambda: "https://api.wandb.ai")

    assert trace_env._wandb_api_key_via_netrc_file(str(netrc_path)) == "netrc-key"


def test_wandb_api_key_via_netrc_file_returns_none_for_non_matching_host(
    tmp_path, monkeypatch
):
    netrc_path = tmp_path / ".netrc"
    _write_netrc(netrc_path, "other.wandb.ai", "netrc-key")
    monkeypatch.setattr(trace_env, "wandb_base_url", lambda: "https://api.wandb.ai")

    assert trace_env._wandb_api_key_via_netrc_file(str(netrc_path)) is None


def test_wandb_api_key_via_netrc_tries_unix_then_windows_paths(monkeypatch):
    observed_paths: list[str] = []

    def _lookup(path: str) -> str | None:
        observed_paths.append(path)
        if path == "~/_netrc":
            return "windows-key"
        return None

    monkeypatch.setattr(trace_env, "_wandb_api_key_via_netrc_file", _lookup)

    assert trace_env._wandb_api_key_via_netrc() == "windows-key"
    assert observed_paths == ["~/.netrc", "~/_netrc"]


def test_wandb_api_key_via_netrc_stops_after_first_match(monkeypatch):
    observed_paths: list[str] = []

    def _lookup(path: str) -> str | None:
        observed_paths.append(path)
        if path == "~/.netrc":
            return "unix-key"
        pytest.fail("unexpected lookup after finding an API key")

    monkeypatch.setattr(trace_env, "_wandb_api_key_via_netrc_file", _lookup)

    assert trace_env._wandb_api_key_via_netrc() == "unix-key"
    assert observed_paths == ["~/.netrc"]


def test_weave_wandb_api_key_prefers_env_value(monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "env-key")

    def _unexpected_netrc_lookup() -> str | None:
        pytest.fail("netrc lookup should not run when WANDB_API_KEY is set")

    monkeypatch.setattr(trace_env, "_wandb_api_key_via_netrc", _unexpected_netrc_lookup)

    assert trace_env.weave_wandb_api_key() == "env-key"


def test_weave_wandb_api_key_uses_netrc_when_env_var_is_empty(monkeypatch):
    monkeypatch.setenv("WANDB_API_KEY", "")
    monkeypatch.setattr(trace_env, "_wandb_api_key_via_netrc", lambda: "netrc-key")

    assert trace_env.weave_wandb_api_key() == "netrc-key"
