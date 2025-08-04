"""Shared fixtures for wandb compatibility tests."""

import configparser
from unittest.mock import Mock, patch

import pytest

from .test_fixtures import HostAndBaseURL


@pytest.fixture
def api_key(request):
    """Parametrized fixture for different API key formats."""
    if request.param == "valid-saas":
        return "a" * 40
    elif request.param == "valid-onprem":
        return "local-" + "b" * 40
    elif request.param == "invalid-too-short":
        return "short"
    elif request.param == "invalid-too-long":
        return "a" * 41
    elif request.param == "invalid-onprem-too-short":
        return "local-short"
    elif request.param == "invalid-onprem-too-long":
        return "local-" + "c" * 41

    raise ValueError(f"Invalid API key type: {request.param}")


@pytest.fixture
def host_and_base_url(request):
    """Parametrized fixture for different host configurations."""
    if request.param == "saas":
        base_url = "https://api.wandb.ai"
        host = "api.wandb.ai"
    elif request.param == "aws":
        base_url = "https://example-aws.wandb.io"
        host = "example-aws.wandb.io"
    elif request.param == "gcp":
        base_url = "https://example-gcp.wandb.io"
        host = "example-gcp.wandb.io"
    elif request.param == "azure":
        base_url = "https://example-azure.wandb.io"
        host = "example-azure.wandb.io"
    elif request.param == "onprem":
        base_url = "https://wandb.customer.com"
        host = "wandb.customer.com"
    else:
        raise ValueError(f"Invalid host type: {request.param}")

    return HostAndBaseURL(host, base_url)


@pytest.fixture
def mock_netrc():
    """Fixture that provides a mocked Netrc instance."""
    with patch("weave.compat.wandb.wandb_thin.login.Netrc") as mock_netrc_class:
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
    with patch.dict("os.environ", {"WANDB_CONFIG_DIR": str(tmp_path)}):
        yield tmp_path


@pytest.fixture
def create_settings_file(temp_config_dir):
    """Fixture that creates a settings file with given content."""

    def _create_settings_file(settings_dict):
        settings_path = temp_config_dir / "settings"
        config = configparser.ConfigParser()
        config.add_section("default")

        for key, value in settings_dict.items():
            config.set("default", key, value)

        with open(settings_path, "w") as f:
            config.write(f)

        return settings_path

    return _create_settings_file
