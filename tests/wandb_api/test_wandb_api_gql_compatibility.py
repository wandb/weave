"""Test gql 3.x and 4.x compatibility in wandb_api module."""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import importlib


class TestGqlCompatibility(unittest.TestCase):
    """Test that wandb_api works with both gql 3.x and 4.x."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any cached imports
        if 'weave.wandb_interface.wandb_api' in sys.modules:
            del sys.modules['weave.wandb_interface.wandb_api']

    def test_gql_v3_sync_execute(self):
        """Test that gql 3.x style execute() calls work."""
        with patch('weave.wandb_interface.wandb_api.GQL_V4_PLUS', False):
            with patch('weave.wandb_interface.wandb_api.RequestsHTTPTransport'):
                with patch('weave.wandb_interface.wandb_api.gql.Client') as mock_client:
                    # Mock the session and execute
                    mock_session = MagicMock()
                    mock_client.return_value.connect_sync.return_value = mock_session
                    mock_session.execute.return_value = {"data": "test"}
                    
                    # Import after patching
                    from weave.wandb_interface import wandb_api
                    
                    # Create API instance and test query
                    api = wandb_api.WandbApi()
                    mock_query = MagicMock()
                    result = api.query(mock_query, test_param="value")
                    
                    # Verify gql 3.x style call (positional argument)
                    mock_session.execute.assert_called_once_with(mock_query, {"test_param": "value"})
                    self.assertEqual(result, {"data": "test"})

    def test_gql_v4_sync_execute(self):
        """Test that gql 4.x style execute() calls work."""
        with patch('weave.wandb_interface.wandb_api.GQL_V4_PLUS', True):
            with patch('weave.wandb_interface.wandb_api.RequestsHTTPTransport'):
                with patch('weave.wandb_interface.wandb_api.gql.Client') as mock_client:
                    # Mock the session and execute
                    mock_session = MagicMock()
                    mock_client.return_value.connect_sync.return_value = mock_session
                    mock_session.execute.return_value = {"data": "test"}
                    
                    # Import after patching
                    from weave.wandb_interface import wandb_api
                    
                    # Create API instance and test query
                    api = wandb_api.WandbApi()
                    mock_query = MagicMock()
                    result = api.query(mock_query, test_param="value")
                    
                    # Verify gql 4.x style call (keyword argument)
                    mock_session.execute.assert_called_once_with(
                        mock_query, variable_values={"test_param": "value"}
                    )
                    self.assertEqual(result, {"data": "test"})

    @patch('weave.wandb_interface.wandb_api.aiohttp.TCPConnector')
    async def test_gql_v3_async_execute(self, mock_connector):
        """Test that gql 3.x style async execute() calls work."""
        with patch('weave.wandb_interface.wandb_api.GQL_V4_PLUS', False):
            with patch('weave.wandb_interface.wandb_api.AIOHTTPTransport') as mock_transport:
                with patch('weave.wandb_interface.wandb_api.gql.Client') as mock_client:
                    # Mock the session and execute
                    mock_session = AsyncMock()
                    mock_client.return_value.connect_async = AsyncMock(return_value=mock_session)
                    mock_session.execute = AsyncMock(return_value={"data": "test"})
                    mock_transport.return_value.session.close = AsyncMock()
                    
                    # Import after patching
                    from weave.wandb_interface import wandb_api
                    
                    # Test async query
                    mock_query = MagicMock()
                    result = await wandb_api.query_with_retry(
                        mock_query, "http://test.com", test_param="value"
                    )
                    
                    # Verify gql 3.x style call (positional argument)
                    mock_session.execute.assert_called_once_with(mock_query, {"test_param": "value"})
                    self.assertEqual(result, {"data": "test"})

    @patch('weave.wandb_interface.wandb_api.aiohttp.TCPConnector')
    async def test_gql_v4_async_execute(self, mock_connector):
        """Test that gql 4.x style async execute() calls work."""
        with patch('weave.wandb_interface.wandb_api.GQL_V4_PLUS', True):
            with patch('weave.wandb_interface.wandb_api.AIOHTTPTransport') as mock_transport:
                with patch('weave.wandb_interface.wandb_api.gql.Client') as mock_client:
                    # Mock the session and execute
                    mock_session = AsyncMock()
                    mock_client.return_value.connect_async = AsyncMock(return_value=mock_session)
                    mock_session.execute = AsyncMock(return_value={"data": "test"})
                    mock_transport.return_value.session.close = AsyncMock()
                    
                    # Import after patching
                    from weave.wandb_interface import wandb_api
                    
                    # Test async query
                    mock_query = MagicMock()
                    result = await wandb_api.query_with_retry(
                        mock_query, "http://test.com", test_param="value"
                    )
                    
                    # Verify gql 4.x style call (keyword argument)
                    mock_session.execute.assert_called_once_with(
                        mock_query, variable_values={"test_param": "value"}
                    )
                    self.assertEqual(result, {"data": "test"})

    def test_gql_version_detection(self):
        """Test that gql version is properly detected."""
        # Test with __version__ attribute
        with patch('weave.wandb_interface.wandb_api.gql') as mock_gql:
            mock_gql.__version__ = '4.0.0'
            # Force reimport to get new version detection
            importlib.reload(sys.modules['weave.wandb_interface.wandb_api'])
            from weave.wandb_interface import wandb_api
            self.assertTrue(wandb_api.GQL_V4_PLUS)
            
        # Test with version 3.x
        with patch('weave.wandb_interface.wandb_api.gql') as mock_gql:
            mock_gql.__version__ = '3.4.1'
            importlib.reload(sys.modules['weave.wandb_interface.wandb_api'])
            from weave.wandb_interface import wandb_api
            self.assertFalse(wandb_api.GQL_V4_PLUS)
            
        # Test without __version__ attribute (defaults to 3.x)
        with patch('weave.wandb_interface.wandb_api.gql') as mock_gql:
            del mock_gql.__version__
            importlib.reload(sys.modules['weave.wandb_interface.wandb_api'])
            from weave.wandb_interface import wandb_api
            self.assertFalse(wandb_api.GQL_V4_PLUS)


if __name__ == '__main__':
    unittest.main()
