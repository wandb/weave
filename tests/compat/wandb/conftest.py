"""Shared fixtures for wandb compatibility tests."""

import importlib
import os
from unittest.mock import Mock, patch

import pytest

# Import the submodule explicitly to dodge a Python 3.10/3.11 quirk: the parent
# package's __init__.py does `from .login import login`, which makes
# `wandb_thin.login` resolve to the function (not the submodule). On those
# versions mock.patch's getattr-walk then trips on `login._set_setting`. Using
# patch.object against the actual module is portable across all versions.
_login_module = importlib.import_module("weave.compat.wandb.wandb_thin.login")
_util_module = importlib.import_module("weave.compat.wandb.wandb_thin.util")


@pytest.fixture
def mock_netrc():
    """Fixture that provides a mocked Netrc instance."""
    with patch.object(_login_module, "Netrc", autospec=True) as mock_netrc_class:
        mock_netrc_instance = Mock()
        mock_netrc_class.return_value = mock_netrc_instance
        yield mock_netrc_instance


@pytest.fixture
def mock_default_host():
    """Fixture that mocks _get_default_host to return api.wandb.ai."""
    with patch.object(_login_module, "_get_default_host", return_value="api.wandb.ai"):
        yield


@pytest.fixture
def mock_app_url():
    """Fixture that mocks app_url to return https://wandb.ai."""
    with patch.object(_util_module, "app_url", return_value="https://wandb.ai"):
        yield


@pytest.fixture
def temp_config_dir(tmp_path):
    """Fixture that provides a temporary config directory."""
    with patch.dict(os.environ, {"WANDB_CONFIG_DIR": str(tmp_path)}, clear=True):
        yield tmp_path
