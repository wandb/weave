from __future__ import annotations

import httpx
import pytest

from weave.utils import http_requests


@pytest.fixture(autouse=True)
def clear_proxy_env(monkeypatch):
    for var_name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "no_proxy",
    ):
        monkeypatch.delenv(var_name, raising=False)


def test_proxy_resolution_uses_scheme_specific_env(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8443")

    proxy = http_requests._get_proxy_for_url(httpx.URL("https://api.wandb.ai/calls"))

    assert proxy == "http://proxy.example:8443"


def test_proxy_resolution_falls_back_to_all_proxy(monkeypatch):
    monkeypatch.setenv("ALL_PROXY", "http://proxy.example:8080")

    proxy = http_requests._get_proxy_for_url(httpx.URL("https://api.wandb.ai/calls"))

    assert proxy == "http://proxy.example:8080"


def test_proxy_resolution_uses_http_proxy_for_http_urls(monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example:8080")

    proxy = http_requests._get_proxy_for_url(httpx.URL("http://api.wandb.ai/calls"))

    assert proxy == "http://proxy.example:8080"


def test_proxy_resolution_respects_no_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example:8443")
    monkeypatch.setenv("NO_PROXY", "api.wandb.ai")

    proxy = http_requests._get_proxy_for_url(httpx.URL("https://api.wandb.ai/calls"))

    assert proxy is None
