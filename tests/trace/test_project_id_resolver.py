"""Tests for ProjectIdResolver: caching, disabling, error handling."""

from __future__ import annotations

import logging
from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest

from weave.trace.project_id_resolver import ProjectIdResolver, ResolverDisabledError
from weave.trace_server.errors import DigestMismatchError


@pytest.fixture(autouse=True)
def enable_client_side_digests(monkeypatch):
    monkeypatch.setenv("WEAVE_ENABLE_CLIENT_SIDE_DIGESTS", "true")


def test_cache_miss_hit_and_per_project() -> None:
    resolver = _make_resolver("int-abc")

    # miss hits the server and returns the resolved id
    assert resolver.resolve("entity/proj") == "int-abc"
    assert resolver._server.projects_info.call_count == 1

    # second resolve of the same project is served from cache
    assert resolver.resolve("entity/proj") == "int-abc"
    assert resolver._server.projects_info.call_count == 1

    # a distinct project is cached separately, so it misses
    resolver.resolve("entity/proj-b")
    assert resolver._server.projects_info.call_count == 2


def test_attribute_error_permanently_disables() -> None:
    server = MagicMock()
    server.projects_info.side_effect = AttributeError("no such method")
    resolver = ProjectIdResolver(server)

    assert resolver.resolve("entity/proj") is None
    assert resolver.is_disabled


def test_transient_and_empty_results_not_cached() -> None:
    # transient errors are not cached: a later success re-queries and resolves
    server = MagicMock()
    server.projects_info.side_effect = TimeoutError("network timeout")
    resolver = ProjectIdResolver(server)

    assert resolver.resolve("entity/proj") is None
    assert not resolver.is_disabled

    mock_result = MagicMock()
    mock_result.internal_project_id = "int-abc"
    server.projects_info.side_effect = None
    server.projects_info.return_value = [mock_result]

    assert resolver.resolve("entity/proj") == "int-abc"
    assert server.projects_info.call_count == 2

    # empty results are likewise not cached, so a repeat re-queries
    empty_server = MagicMock()
    empty_server.projects_info.return_value = []
    empty_resolver = ProjectIdResolver(empty_server)

    assert empty_resolver.resolve("entity/proj") is None
    empty_resolver.resolve("entity/proj")
    assert empty_server.projects_info.call_count == 2


def test_disable_enable_and_idempotent_validation_error(caplog) -> None:
    resolver = _make_resolver("int-abc")
    resolver.resolve("entity/proj")

    # disabling makes resolve raise but get_internal_project_id return None
    resolver.disable()
    with pytest.raises(ResolverDisabledError):
        resolver.resolve("entity/proj")
    assert resolver.get_internal_project_id("entity/proj") is None

    # re-enabling restores lookups
    resolver.enable()
    assert resolver.resolve("entity/proj") == "int-abc"

    # disable_after_validation_error clears the cache, disables, warns once
    resolver._cache["a/b"] = "cached-id"
    caplog.set_level(logging.WARNING, logger="weave.trace.project_id_resolver")
    exc = DigestMismatchError("mismatch")
    resolver.disable_after_validation_error(exc, "ref1")
    resolver.disable_after_validation_error(exc, "ref2")

    assert resolver.is_disabled
    assert len(resolver._cache) == 0
    warnings = [r for r in caplog.records if "disabling fast path" in r.getMessage()]
    assert len(warnings) == 1


@pytest.mark.parametrize(
    ("exc", "result", "expect_disabled"),
    [
        (DigestMismatchError("mismatch"), None, True),
        (ValueError("unrelated"), None, False),
        (None, MagicMock(), False),
    ],
)
def test_on_fire_and_forget_done(exc, result, expect_disabled) -> None:
    resolver = _make_resolver("int-abc")
    future: Future = Future()
    if exc is not None:
        future.set_exception(exc)
    else:
        future.set_result(result)

    resolver.on_fire_and_forget_done(future, ref_uri="weave:///a/b/obj")

    assert resolver.is_disabled is expect_disabled


def _make_resolver(internal_id: str) -> ProjectIdResolver:
    server = MagicMock()
    result = MagicMock()
    result.internal_project_id = internal_id
    server.projects_info.return_value = [result]
    return ProjectIdResolver(server)
