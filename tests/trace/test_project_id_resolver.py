"""Tests for ProjectIdResolver: caching, disabling, error handling."""

from __future__ import annotations

import logging
from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest

from weave.trace.project_id_resolver import ProjectIdResolver, ResolverDisabledError
from weave.trace.settings import (
    UserSettings,
    parse_and_apply_settings,
)
from weave.trace_server.errors import DigestMismatchError


@pytest.fixture(autouse=True)
def enable_client_side_digests():
    parse_and_apply_settings(UserSettings(enable_client_side_digests=True))
    yield
    parse_and_apply_settings(UserSettings())


def _make_resolver(internal_id: str) -> ProjectIdResolver:
    server = MagicMock()
    result = MagicMock()
    result.internal_project_id = internal_id
    server.projects_info.return_value = [result]
    return ProjectIdResolver(server)


class TestCache:
    def test_calls_server_on_miss(self) -> None:
        resolver = _make_resolver("int-abc")
        result = resolver.resolve("entity/proj")

        assert result == "int-abc"
        resolver._server.projects_info.assert_called_once()

    def test_returns_cached_on_hit(self) -> None:
        resolver = _make_resolver("int-abc")
        resolver.resolve("entity/proj")
        resolver.resolve("entity/proj")

        assert resolver._server.projects_info.call_count == 1

    def test_caches_per_project(self) -> None:
        resolver = _make_resolver("int-abc")
        resolver.resolve("entity/proj-a")
        resolver.resolve("entity/proj-b")

        assert resolver._server.projects_info.call_count == 2


class TestErrorHandling:
    def test_attribute_error_permanently_disables(self) -> None:
        server = MagicMock()
        server.projects_info.side_effect = AttributeError("no such method")
        resolver = ProjectIdResolver(server)

        result = resolver.resolve("entity/proj")

        assert result is None
        assert resolver.is_disabled

    def test_transient_error_not_cached(self) -> None:
        server = MagicMock()
        server.projects_info.side_effect = TimeoutError("network timeout")
        resolver = ProjectIdResolver(server)

        result1 = resolver.resolve("entity/proj")
        assert result1 is None
        assert not resolver.is_disabled

        mock_result = MagicMock()
        mock_result.internal_project_id = "int-abc"
        server.projects_info.side_effect = None
        server.projects_info.return_value = [mock_result]

        result2 = resolver.resolve("entity/proj")
        assert result2 == "int-abc"
        assert server.projects_info.call_count == 2

    def test_empty_result_not_cached(self) -> None:
        server = MagicMock()
        server.projects_info.return_value = []
        resolver = ProjectIdResolver(server)

        result = resolver.resolve("entity/proj")
        assert result is None

        resolver.resolve("entity/proj")
        assert server.projects_info.call_count == 2


class TestDisable:
    def test_disable_makes_resolve_raise(self) -> None:
        resolver = _make_resolver("int-abc")
        resolver.resolve("entity/proj")

        resolver.disable()

        with pytest.raises(ResolverDisabledError):
            resolver.resolve("entity/proj")

    def test_disable_makes_get_internal_project_id_return_none(self) -> None:
        resolver = _make_resolver("int-abc")
        resolver.disable()

        assert resolver.get_internal_project_id("entity/proj") is None

    def test_enable_restores_lookups(self) -> None:
        resolver = _make_resolver("int-abc")
        resolver.disable()
        resolver.enable()

        result = resolver.resolve("entity/proj")
        assert result == "int-abc"

    def test_disable_after_validation_error_is_idempotent(self, caplog) -> None:
        resolver = _make_resolver("int-abc")
        resolver._cache["a/b"] = "cached-id"
        caplog.set_level(logging.WARNING, logger="weave.trace.project_id_resolver")

        exc = DigestMismatchError("mismatch")
        resolver.disable_after_validation_error(exc, "ref1")
        resolver.disable_after_validation_error(exc, "ref2")

        assert resolver.is_disabled
        assert len(resolver._cache) == 0
        warnings = [
            r for r in caplog.records if "disabling fast path" in r.getMessage()
        ]
        assert len(warnings) == 1


class TestOnFireAndForgetDone:
    def test_disables_on_digest_mismatch(self) -> None:
        resolver = _make_resolver("int-abc")
        future: Future = Future()
        future.set_exception(DigestMismatchError("mismatch"))

        resolver.on_fire_and_forget_done(future, ref_uri="weave:///a/b/obj")

        assert resolver.is_disabled

    def test_ignores_non_digest_errors(self) -> None:
        resolver = _make_resolver("int-abc")
        future: Future = Future()
        future.set_exception(ValueError("unrelated"))

        resolver.on_fire_and_forget_done(future, ref_uri="weave:///a/b/obj")

        assert not resolver.is_disabled

    def test_ignores_success(self) -> None:
        resolver = _make_resolver("int-abc")
        future: Future = Future()
        future.set_result(MagicMock())

        resolver.on_fire_and_forget_done(future, ref_uri="weave:///a/b/obj")

        assert not resolver.is_disabled
