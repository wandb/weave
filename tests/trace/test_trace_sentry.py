"""Tests for the trace_sentry module."""

import unittest
from unittest import mock

import sentry_sdk

from weave.trace import trace_sentry


class TestDualSentryReporting(unittest.TestCase):
    """Test that events are sent to both Weave's Sentry endpoint and user's endpoint when configured."""

    def setUp(self):
        # Mock Hub and Client to avoid actual Sentry calls
        self.mock_hub_patcher = mock.patch("sentry_sdk.Hub")
        self.mock_hub = self.mock_hub_patcher.start()

        # Mock Hub.current to simulate user-configured Sentry
        self.mock_hub.current = mock.MagicMock()
        self.mock_hub.current.client = mock.MagicMock()

        # Mock event_from_exception
        self.mock_event_from_exception_patcher = mock.patch(
            "sentry_sdk.utils.event_from_exception"
        )
        self.mock_event_from_exception = self.mock_event_from_exception_patcher.start()
        self.mock_event_from_exception.return_value = (
            {"event": "data"},
            {"hint": "data"},
        )

        # Mock exc_info_from_error
        self.mock_exc_info_patcher = mock.patch("sentry_sdk.utils.exc_info_from_error")
        self.mock_exc_info = self.mock_exc_info_patcher.start()

        # Reset the global Sentry instance to ensure clean test state
        self.original_sentry = trace_sentry.global_trace_sentry
        trace_sentry.global_trace_sentry = trace_sentry.Sentry()

        # Store original is_sentry_configured function
        self.original_is_sentry_configured = trace_sentry._is_sentry_configured

    def tearDown(self):
        self.mock_hub_patcher.stop()
        self.mock_event_from_exception_patcher.stop()
        self.mock_exc_info_patcher.stop()
        # Restore the global Sentry instance
        trace_sentry.global_trace_sentry = self.original_sentry
        # Restore the original is_sentry_configured function
        trace_sentry._is_sentry_configured = self.original_is_sentry_configured

    def test_setup_creates_both_hubs_when_user_configured(self):
        """Test that setup creates both hubs when user has configured Sentry."""
        # Mock _is_sentry_configured to return True
        trace_sentry._is_sentry_configured = mock.MagicMock(return_value=True)

        # Setup Sentry
        sentry = trace_sentry.Sentry()
        sentry.setup()

        # Verify that setup used the existing hub and created a new weave hub
        self.assertEqual(sentry.hub, sentry_sdk.Hub.current)
        self.assertTrue(sentry._using_global_hub)
        self.assertIsNotNone(sentry.weave_hub)

    def test_setup_creates_single_hub_when_no_user_config(self):
        """Test that setup creates a single hub when user has not configured Sentry."""
        # Mock _is_sentry_configured to return False
        trace_sentry._is_sentry_configured = mock.MagicMock(return_value=False)

        # Setup Sentry
        sentry = trace_sentry.Sentry()
        sentry.setup()

        # Verify that setup created a new hub and did not create a separate weave hub
        self.assertIsNotNone(sentry.hub)
        self.assertFalse(sentry._using_global_hub)
        self.assertIsNone(sentry.weave_hub)

    def test_exception_reports_to_both_hubs_when_user_configured(self):
        """Test that exception is reported to both hubs when user has configured Sentry."""
        # Mock _is_sentry_configured to return True
        trace_sentry._is_sentry_configured = mock.MagicMock(return_value=True)

        # Create a sentry instance with mocked components
        sentry = trace_sentry.Sentry()

        # Set up the hub and weave_hub manually with proper mocks
        sentry.hub = mock.MagicMock()
        sentry.hub._stack = [(mock.MagicMock(), mock.MagicMock())]
        sentry.hub.client.options = {}
        sentry.hub.capture_event = mock.MagicMock()

        sentry.weave_hub = mock.MagicMock()
        sentry.weave_hub._stack = [(mock.MagicMock(), mock.MagicMock())]
        sentry.weave_hub.capture_event = mock.MagicMock()

        # Mark as using global hub
        sentry._using_global_hub = True

        # Report an exception
        test_error = ValueError("Test error")
        sentry.exception(test_error)

        # Verify that exception was captured by both hubs
        self.assertEqual(sentry.hub.capture_event.call_count, 1)
        self.assertEqual(sentry.weave_hub.capture_event.call_count, 1)

    def test_track_event_reports_to_both_hubs_when_user_configured(self):
        """Test that track_event reports to both hubs when user has configured Sentry."""
        # Mock _is_sentry_configured to return True
        trace_sentry._is_sentry_configured = mock.MagicMock(return_value=True)

        # Create a sentry instance
        sentry = trace_sentry.Sentry()

        # Set up the hub and weave_hub manually
        sentry.hub = mock.MagicMock()
        sentry.hub.capture_event = mock.MagicMock()

        sentry.weave_hub = mock.MagicMock()
        sentry.weave_hub.capture_event = mock.MagicMock()

        # Track an event
        sentry.track_event("test_event", {"tag": "value"}, "test_user")

        # Verify that event was captured by both hubs
        self.assertEqual(sentry.hub.capture_event.call_count, 1)
        self.assertEqual(sentry.weave_hub.capture_event.call_count, 1)

    def test_configure_scope_sets_up_both_hubs_when_user_configured(self):
        """Test that configure_scope sets up both hubs when user has configured Sentry."""
        # Mock _is_sentry_configured to return True
        trace_sentry._is_sentry_configured = mock.MagicMock(return_value=True)

        # Create a sentry instance
        sentry = trace_sentry.Sentry()

        # Set up the hub and weave_hub manually
        sentry.hub = mock.MagicMock()
        sentry.hub._stack = [(mock.MagicMock(), mock.MagicMock())]

        # Mock configure_scope context managers
        user_scope = mock.MagicMock()
        sentry.hub.configure_scope.return_value.__enter__.return_value = user_scope

        sentry.weave_hub = mock.MagicMock()
        sentry.weave_hub._stack = [(mock.MagicMock(), mock.MagicMock())]

        weave_scope = mock.MagicMock()
        sentry.weave_hub.configure_scope.return_value.__enter__.return_value = (
            weave_scope
        )

        # Configure scope with tags
        test_tags = {
            "entity_name": "test_entity",
            "project_name": "test_project",
            "user": {"username": "test_user"},
        }
        sentry.configure_scope(test_tags)

        # Verify that tags were set on both scopes
        for tag, value in test_tags.items():
            if tag != "user":
                user_scope.set_tag.assert_any_call(tag, value)
                weave_scope.set_tag.assert_any_call(tag, value)

        # Verify that user was set on both scopes if present
        if "user" in test_tags:
            self.assertEqual(user_scope.user, test_tags["user"])
            self.assertEqual(weave_scope.user, test_tags["user"])

    def test_initialize_sentry_respects_user_config_and_adds_weave(self):
        """Test that initialize_sentry respects user config and adds Weave reporting."""
        # Mock _is_sentry_configured to return True
        trace_sentry._is_sentry_configured = mock.MagicMock(return_value=True)

        # Create a mock for setup and configure_scope
        with (
            mock.patch.object(trace_sentry.global_trace_sentry, "setup") as mock_setup,
            mock.patch.object(
                trace_sentry.global_trace_sentry, "configure_scope"
            ) as mock_configure_scope,
        ):
            # Call initialize_sentry
            trace_sentry.initialize_sentry()

            # Verify that setup and configure_scope were called
            mock_setup.assert_called_once()
            mock_configure_scope.assert_called_once()
