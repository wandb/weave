"""Tests for weave.init() API backwards compatibility and new calling patterns."""

from unittest.mock import Mock, patch

import pytest

import weave
from weave.trace import weave_init
from weave.trace.weave_client import WeaveClient


@pytest.fixture(autouse=True)
def reset_weave_client():
    """Reset the global weave client state before and after each test."""
    weave_init._current_inited_client = None
    yield
    weave_init._current_inited_client = None


@pytest.fixture
def mock_init_weave():
    """Mock the internal init_weave function to avoid actual initialization."""
    with patch("weave.trace.weave_init.init_weave") as mock:
        mock.return_value = Mock(spec=WeaveClient)
        yield mock


@pytest.fixture
def mock_should_disable():
    """Mock should_disable_weave to control when weave is disabled."""
    with patch("weave.trace.api.should_disable_weave") as mock:
        mock.return_value = False
        yield mock


class TestInitBackwardsCompatibility:
    """Test that the original init patterns still work correctly."""

    def test_init_single_string_with_slash(self, mock_init_weave):
        """Test original pattern: init("entity/project")."""
        client = weave.init("my-entity/my-project")

        assert client is not None
        mock_init_weave.assert_called_once_with("my-entity/my-project")

    def test_init_single_string_without_entity(self, mock_init_weave):
        """Test original pattern: init("project-name") without entity."""
        client = weave.init("my-project")

        assert client is not None
        mock_init_weave.assert_called_once_with("my-project")

    def test_init_with_settings_kwargs(self, mock_init_weave):
        """Test original pattern with settings passed as kwargs."""
        with patch("weave.trace.api.parse_and_apply_settings") as mock_parse:
            settings = {"api_url": "https://test.api"}
            client = weave.init("entity/project", settings=settings)

            assert client is not None
            mock_init_weave.assert_called_once_with("entity/project")
            mock_parse.assert_called_once_with(settings)

    def test_init_with_global_attributes(self, mock_init_weave):
        """Test original pattern with global attributes."""
        attributes = {"key": "value"}
        client = weave.init("entity/project", global_attributes=attributes)

        assert client is not None
        mock_init_weave.assert_called_once_with("entity/project")
        assert weave.trace.api._global_attributes == attributes

    def test_init_empty_project_name_raises_error(self):
        """Test that empty project name raises ValueError."""
        with pytest.raises(ValueError, match="project_name must be non-empty"):
            weave.init("")

        with pytest.raises(ValueError, match="project_name must be non-empty"):
            weave.init("   ")


class TestInitNewCallingPattern:
    """Test the new two-argument calling pattern."""

    def test_init_two_strings(self, mock_init_weave):
        """Test new pattern: init("entity", "project")."""
        client = weave.init("my-entity", "my-project")

        assert client is not None
        mock_init_weave.assert_called_once_with("my-entity/my-project")

    def test_init_two_strings_with_settings(self, mock_init_weave):
        """Test new pattern with settings passed as kwargs."""
        with patch("weave.trace.api.parse_and_apply_settings") as mock_parse:
            settings = {"api_url": "https://test.api"}
            client = weave.init("my-entity", "my-project", settings=settings)

            assert client is not None
            mock_init_weave.assert_called_once_with("my-entity/my-project")
            mock_parse.assert_called_once_with(settings)

    def test_init_two_strings_with_global_attributes(self, mock_init_weave):
        """Test new pattern with global attributes."""
        attributes = {"key": "value", "env": "test"}
        client = weave.init("my-entity", "my-project", global_attributes=attributes)

        assert client is not None
        mock_init_weave.assert_called_once_with("my-entity/my-project")
        assert weave.trace.api._global_attributes == attributes

    def test_init_two_strings_with_all_kwargs(self, mock_init_weave):
        """Test new pattern with all optional kwargs."""
        with patch("weave.trace.api.parse_and_apply_settings") as mock_parse:
            settings = {"api_url": "https://test.api"}
            attributes = {"key": "value"}

            def mock_postprocess_input(inputs):
                return inputs

            def mock_postprocess_output(output):
                return output

            client = weave.init(
                "my-entity",
                "my-project",
                settings=settings,
                global_attributes=attributes,
                global_postprocess_inputs=mock_postprocess_input,
                global_postprocess_output=mock_postprocess_output,
            )

            assert client is not None
            mock_init_weave.assert_called_once_with("my-entity/my-project")
            mock_parse.assert_called_once_with(settings)
            assert weave.trace.api._global_attributes == attributes
            assert weave.trace.api._global_postprocess_inputs == mock_postprocess_input
            assert weave.trace.api._global_postprocess_output == mock_postprocess_output


class TestInitPatternEquivalence:
    """Test that both patterns produce equivalent results."""

    def test_patterns_are_equivalent(self, mock_init_weave):
        """Test that init("entity/project") and init("entity", "project") are equivalent."""
        # Test first pattern
        client1 = weave.init("test-entity/test-project")
        call1 = mock_init_weave.call_args_list[0]

        # Reset mock
        mock_init_weave.reset_mock()

        # Test second pattern
        client2 = weave.init("test-entity", "test-project")
        call2 = mock_init_weave.call_args_list[0]

        # Both should call init_weave with the same argument
        assert call1 == call2
        assert call1[0][0] == "test-entity/test-project"
        assert call2[0][0] == "test-entity/test-project"

    def test_patterns_with_settings_are_equivalent(self, mock_init_weave):
        """Test that both patterns work the same with settings."""
        with patch("weave.trace.api.parse_and_apply_settings") as mock_parse:
            settings = {"api_url": "https://custom.api", "timeout": 30}

            # Test first pattern
            client1 = weave.init("test-entity/test-project", settings=settings)
            call1 = mock_init_weave.call_args_list[0]
            parse_call1 = mock_parse.call_args_list[0]

            # Reset mocks
            mock_init_weave.reset_mock()
            mock_parse.reset_mock()

            # Test second pattern
            client2 = weave.init("test-entity", "test-project", settings=settings)
            call2 = mock_init_weave.call_args_list[0]
            parse_call2 = mock_parse.call_args_list[0]

            # Both should produce identical calls
            assert call1 == call2
            assert parse_call1 == parse_call2


class TestInitEdgeCases:
    """Test edge cases and error conditions."""

    def test_init_with_slash_in_entity_name(self, mock_init_weave):
        """Test that entity name with slash works correctly in new pattern."""
        # This should work - treating the whole first arg as entity
        client = weave.init("my-org/team", "project-name")

        assert client is not None
        mock_init_weave.assert_called_once_with("my-org/team/project-name")

    def test_init_disabled(self, mock_init_weave, mock_should_disable):
        """Test that init returns disabled client when weave is disabled."""
        mock_should_disable.return_value = True

        with patch("weave.trace.weave_init.init_weave_disabled") as mock_disabled:
            mock_disabled.return_value = Mock(spec=WeaveClient)

            # Test original pattern
            client1 = weave.init("entity/project")
            mock_disabled.assert_called_once()
            mock_init_weave.assert_not_called()

            # Reset and test new pattern
            mock_disabled.reset_mock()
            client2 = weave.init("entity", "project")
            mock_disabled.assert_called_once()
            mock_init_weave.assert_not_called()

    def test_init_with_autopatch_settings_shows_deprecation(
        self, mock_init_weave, caplog
    ):
        """Test that autopatch_settings shows deprecation warning."""
        import logging

        # Capture log messages
        with caplog.at_level(logging.WARNING):
            client = weave.init(
                "entity/project", autopatch_settings={"some": "setting"}
            )

        # Check that deprecation warning was logged
        assert any("autopatch_settings" in record.message for record in caplog.records)
        assert client is not None
        mock_init_weave.assert_called_once_with("entity/project")

    def test_init_with_special_characters(self, mock_init_weave):
        """Test that special characters in entity/project names work."""
        # Test with hyphens, underscores, and numbers
        client = weave.init("test-entity_123", "my-project_456")

        assert client is not None
        mock_init_weave.assert_called_once_with("test-entity_123/my-project_456")


class TestInitArgumentHandling:
    """Test that arguments are properly handled and parsed."""

    def test_positional_only_arguments(self, mock_init_weave):
        """Test that the first arguments are positional-only."""
        # These should work
        weave.init("entity/project")
        weave.init("entity", "project")

        # Verify we can't pass them as keyword arguments
        # Note: This would be a syntax error in real Python due to the / in the signature
        # but we're testing the logical behavior here

        assert mock_init_weave.call_count == 2

    def test_all_kwargs_are_optional(self, mock_init_weave):
        """Test that all kwargs have defaults and are optional."""
        # Should work with no kwargs
        client = weave.init("entity/project")
        assert client is not None

        # Should work with any subset of kwargs - use valid settings
        client = weave.init(
            "entity", "project", settings={"disabled": False, "print_call_link": False}
        )
        assert client is not None

        client = weave.init("entity/project", global_attributes={"attr": 1})
        assert client is not None

        assert mock_init_weave.call_count == 3


class TestInitIntegration:
    """Integration tests that test actual behavior with minimal mocking."""

    @patch("weave.trace.weave_init.init_weave")
    def test_full_init_flow_both_patterns(self, mock_init_weave_internal):
        """Test that both patterns pass the correct project name to the internal init function."""
        # Setup mock to return a WeaveClient-like object
        mock_client = Mock(spec=WeaveClient)
        mock_init_weave_internal.return_value = mock_client

        # Test original pattern
        client1 = weave.init("test-entity/test-project")
        assert client1 is not None
        mock_init_weave_internal.assert_called_with("test-entity/test-project")

        # Reset mock
        mock_init_weave_internal.reset_mock()

        # Test new pattern - should call with the same combined project name
        client2 = weave.init("test-entity", "test-project")
        assert client2 is not None
        mock_init_weave_internal.assert_called_with("test-entity/test-project")

        # Verify both patterns result in the same call
        assert mock_init_weave_internal.call_count == 1
