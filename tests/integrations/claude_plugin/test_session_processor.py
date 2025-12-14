"""Tests for SessionProcessor factory class."""

import pytest
from unittest.mock import MagicMock


class TestSessionProcessorInit:
    """Test SessionProcessor initialization."""

    def test_init_stores_client_and_project(self):
        """Verify client and project are stored."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        processor = SessionProcessor(
            client=mock_client,
            project="entity/project",
            source="plugin",
        )

        assert processor.client is mock_client
        assert processor.project == "entity/project"
        assert processor.source == "plugin"

    def test_init_default_source_is_plugin(self):
        """Verify default source is 'plugin'."""
        from weave.integrations.claude_plugin.session_processor import SessionProcessor

        mock_client = MagicMock()
        processor = SessionProcessor(client=mock_client, project="entity/project")

        assert processor.source == "plugin"
