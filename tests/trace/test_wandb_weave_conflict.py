"""Tests for preventing weave.init conflicts with active wandb runs."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import weave
from weave.trace import weave_init, weave_client
from weave.trace.context import weave_client_context


@pytest.fixture(autouse=True)
def reset_weave_client():
    """Reset the global weave client state before each test."""
    weave_client_context.set_weave_client_global(None)
    yield
    weave_client_context.set_weave_client_global(None)


class TestWandbWeaveConflictPrevention:
    """Test that weave.init prevents conflicts with active wandb runs."""
    
    def test_check_wandb_run_matches_success(self):
        """Test that check_wandb_run_matches allows matching entity/project."""
        # Should not raise when entity/project match
        wandb_run_id = "entity1/project1/run123"
        weave_client.check_wandb_run_matches(wandb_run_id, "entity1", "project1")
    
    def test_check_wandb_run_matches_different_project(self):
        """Test that check_wandb_run_matches raises for different project."""
        wandb_run_id = "entity1/project1/run123"
        
        with pytest.raises(ValueError, match="Project Mismatch"):
            weave_client.check_wandb_run_matches(wandb_run_id, "entity1", "project2")
    
    def test_check_wandb_run_matches_different_entity(self):
        """Test that check_wandb_run_matches raises for different entity."""
        wandb_run_id = "entity1/project1/run123"
        
        with pytest.raises(ValueError, match="Project Mismatch"):
            weave_client.check_wandb_run_matches(wandb_run_id, "entity2", "project1")
    
    def test_check_wandb_run_matches_no_run(self):
        """Test that check_wandb_run_matches handles no wandb run."""
        # Should not raise when no wandb run is active
        weave_client.check_wandb_run_matches(None, "entity1", "project1")
    
    @patch('weave.trace.weave_client.safe_current_wb_run_id')
    @patch('weave.wandb_interface.context.init')
    @patch('weave.wandb_interface.context.get_wandb_api_context')
    def test_init_with_wandb_run_active_different_project_explicit_entity(
        self, mock_get_context, mock_wandb_init, mock_wandb_run_id
    ):
        """Test that weave.init raises error when wandb run is active with different project (explicit entity)."""
        # Mock an active wandb run with entity1/project1
        mock_wandb_run_id.return_value = "entity1/project1/run123"
        
        # Mock wandb context as authenticated
        mock_context = Mock()
        mock_context.api_key = "test_key"
        mock_get_context.return_value = mock_context
        
        # Try to init weave with different project (explicit entity) - should fail
        with pytest.raises(ValueError) as exc_info:
            weave_init.init_weave("entity1/project2")
            
        assert "Project Mismatch" in str(exc_info.value)
        assert "entity1/project1" in str(exc_info.value)
        assert "entity1/project2" in str(exc_info.value)
    
    @patch('weave.trace.weave_client.safe_current_wb_run_id')
    @patch('weave.wandb_interface.context.init')
    @patch('weave.wandb_interface.context.get_wandb_api_context')
    def test_init_with_wandb_run_active_different_entity(
        self, mock_get_context, mock_wandb_init, mock_wandb_run_id
    ):
        """Test that weave.init raises error when wandb run is active with different entity."""
        # Mock an active wandb run with entity1/project1
        mock_wandb_run_id.return_value = "entity1/project1/run123"
        
        # Mock wandb context as authenticated
        mock_context = Mock()
        mock_context.api_key = "test_key"
        mock_get_context.return_value = mock_context
        
        # Try to init weave with different entity - should fail
        with pytest.raises(ValueError) as exc_info:
            weave_init.init_weave("entity2/project1")
            
        assert "Project Mismatch" in str(exc_info.value)
        assert "entity1/project1" in str(exc_info.value)
        assert "entity2/project1" in str(exc_info.value)
    
    @patch('weave.trace.weave_client.safe_current_wb_run_id')
    @patch('weave.wandb_interface.context.init')
    @patch('weave.wandb_interface.context.get_wandb_api_context')
    @patch('weave.trace_server_bindings.remote_http_trace_server.RemoteHTTPTraceServer.from_env')
    def test_init_with_wandb_run_active_same_project(
        self, mock_server, mock_get_context, mock_wandb_init, mock_wandb_run_id
    ):
        """Test that weave.init succeeds when wandb run is active with same project."""
        # Mock an active wandb run with entity1/project1
        mock_wandb_run_id.return_value = "entity1/project1/run123"
        
        # Mock wandb context as authenticated
        mock_context = Mock()
        mock_context.api_key = "test_key"
        mock_get_context.return_value = mock_context
        
        # Mock the server
        mock_server_instance = Mock()
        mock_resp = Mock()
        mock_resp.project_name = "project1"
        mock_server_instance.ensure_project_exists = Mock(return_value=mock_resp)
        mock_server_instance.server_info = Mock(
            return_value=Mock(min_required_weave_python_version="0.0.0")
        )
        mock_server.return_value = mock_server_instance
        
        # Init weave with same project should succeed
        client = weave_init.init_weave("entity1/project1")
        assert client is not None
        assert client.entity == "entity1"
        assert client.project == "project1"
    
    @patch('weave.trace.weave_client.safe_current_wb_run_id')
    @patch('weave.wandb_interface.context.init')
    @patch('weave.wandb_interface.context.get_wandb_api_context')
    @patch('weave.trace_server_bindings.remote_http_trace_server.RemoteHTTPTraceServer.from_env')
    def test_reinit_with_existing_client_and_wandb_run(
        self, mock_server, mock_get_context, mock_wandb_init, mock_wandb_run_id
    ):
        """Test re-initializing weave with an existing client and active wandb run."""
        # Mock an active wandb run with entity1/project1
        mock_wandb_run_id.return_value = "entity1/project1/run123"
        
        # Mock wandb context as authenticated
        mock_context = Mock()
        mock_context.api_key = "test_key"
        mock_get_context.return_value = mock_context
        
        # Mock the server
        mock_server_instance = Mock()
        mock_resp = Mock()
        mock_resp.project_name = "project1"
        mock_server_instance.ensure_project_exists = Mock(return_value=mock_resp)
        mock_server_instance.server_info = Mock(
            return_value=Mock(min_required_weave_python_version="0.0.0")
        )
        mock_server.return_value = mock_server_instance
        
        # First init with matching project
        client1 = weave_init.init_weave("entity1/project1")
        assert client1 is not None
        
        # Try to reinit with different project - should fail
        with pytest.raises(ValueError) as exc_info:
            weave_init.init_weave("entity1/project2")
            
        assert "Project Mismatch" in str(exc_info.value)
        
        # Reinit with same project should succeed (returns existing client)
        client2 = weave_init.init_weave("entity1/project1")
        assert client2 == client1  # Should return the same client instance
    
    @patch('weave.trace.weave_client.safe_current_wb_run_id')
    @patch('weave.wandb_interface.context.init')
    @patch('weave.wandb_interface.context.get_wandb_api_context')
    def test_init_with_wandb_run_implicit_project_conflict(
        self, mock_get_context, mock_wandb_init, mock_wandb_run_id
    ):
        """Test that weave.init detects conflicts when using implicit project names."""
        # Set up an existing client
        mock_client = Mock()
        mock_client.entity = "entity1"
        mock_client.project = "project1"
        mock_client.ensure_project_exists = True
        weave_client_context.set_weave_client_global(mock_client)
        
        # Mock an active wandb run with entity1/project1
        mock_wandb_run_id.return_value = "entity1/project1/run123"
        
        # Mock wandb context as authenticated
        mock_context = Mock()
        mock_context.api_key = "test_key"
        mock_get_context.return_value = mock_context
        
        # Try to init with just project name that would conflict
        with pytest.raises(ValueError) as exc_info:
            weave_init.init_weave("project2")
            
        assert "Project Mismatch" in str(exc_info.value)
        assert "Cannot call weave.init with project" in str(exc_info.value)
        assert "project2" in str(exc_info.value)