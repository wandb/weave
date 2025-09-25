"""Shared fixtures for wandb compatibility tests."""

import os
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_netrc():
    """Fixture that provides a mocked Netrc instance."""
    with patch(
        "weave.compat.wandb.wandb_thin.login.Netrc",
        autospec=True,
    ) as mock_netrc_class:
        mock_netrc_instance = Mock()
        mock_netrc_class.return_value = mock_netrc_instance
        yield mock_netrc_instance


@pytest.fixture
def mock_default_host():
    """Fixture that mocks _get_default_host to return api.wandb.ai."""
    with patch(
        "weave.compat.wandb.wandb_thin.login._get_default_host",
        return_value="api.wandb.ai",
    ):
        yield


@pytest.fixture
def mock_app_url():
    """Fixture that mocks app_url to return https://wandb.ai."""
    with patch(
        "weave.compat.wandb.wandb_thin.util.app_url",
        return_value="https://wandb.ai",
    ):
        yield


@pytest.fixture
def temp_config_dir(tmp_path):
    """Fixture that provides a temporary config directory."""
    with patch.dict(os.environ, {"WANDB_CONFIG_DIR": str(tmp_path)}, clear=True):
        yield tmp_path
