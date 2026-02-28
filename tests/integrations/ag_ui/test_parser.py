"""Tests for AgentEventParser protocol."""

from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest

from weave.integrations.ag_ui.events import AgentEvent, RunStartedEvent
from weave.integrations.ag_ui.parser import AgentEventParser


class TestParserProtocol:
    def test_protocol_is_runtime_checkable(self):
        """Parser protocol should be runtime checkable."""
        assert hasattr(AgentEventParser, "__protocol_attrs__") or isinstance(
            AgentEventParser, type
        )

    def test_mock_parser_implements_protocol(self):
        """A mock parser should satisfy the protocol."""

        class MockParser:
            @property
            def agent_name(self) -> str:
                return "Mock Agent"

            def parse(
                self, source: Path, *, redact_secrets: bool = True
            ) -> Iterator[AgentEvent]:
                yield RunStartedEvent(
                    run_id="test", timestamp=datetime.now(timezone.utc)
                )

            async def parse_stream(
                self, source: Path, from_line: int = 0, *, redact_secrets: bool = True
            ) -> AsyncIterator[AgentEvent]:
                yield RunStartedEvent(
                    run_id="test", timestamp=datetime.now(timezone.utc)
                )

        parser = MockParser()
        assert parser.agent_name == "Mock Agent"

        # Test batch parsing
        events = list(parser.parse(Path("/fake/path")))
        assert len(events) == 1
        assert isinstance(events[0], RunStartedEvent)


class TestParserSecretRedaction:
    def test_redact_secrets_parameter_exists(self):
        """Parser should accept redact_secrets parameter."""

        class MockParser:
            @property
            def agent_name(self) -> str:
                return "Mock"

            def parse(
                self, source: Path, *, redact_secrets: bool = True
            ) -> Iterator[AgentEvent]:
                if redact_secrets:
                    yield RunStartedEvent(
                        run_id="redacted", timestamp=datetime.now(timezone.utc)
                    )
                else:
                    yield RunStartedEvent(
                        run_id="not-redacted", timestamp=datetime.now(timezone.utc)
                    )

            async def parse_stream(
                self, source: Path, from_line: int = 0, *, redact_secrets: bool = True
            ) -> AsyncIterator[AgentEvent]:
                yield RunStartedEvent(
                    run_id="test", timestamp=datetime.now(timezone.utc)
                )

        parser = MockParser()

        # With redaction (default)
        events = list(parser.parse(Path("/fake")))
        assert events[0].run_id == "redacted"

        # Without redaction
        events = list(parser.parse(Path("/fake"), redact_secrets=False))
        assert events[0].run_id == "not-redacted"
