from __future__ import annotations

import configparser
import logging
import netrc
import os
from urllib.parse import urlparse

WEAVE_PARALLELISM = "WEAVE_PARALLELISM"

logger = logging.getLogger(__name__)


class Settings:
    """A minimal readonly implementation of wandb/old/settings.py for reading settings"""

    DEFAULT_SECTION = "default"
    DEFAULT_BASE_URL = "https://api.wandb.ai"

    def __init__(self) -> None:
        self._settings = configparser.ConfigParser()
        if not self._settings.has_section(self.DEFAULT_SECTION):
            self._settings.add_section(self.DEFAULT_SECTION)
        self._settings.read([Settings._global_path(), Settings._local_path()])

    @property
    def base_url(self) -> str:
        try:
            return self._settings.get(self.DEFAULT_SECTION, "base_url")
        except configparser.NoOptionError:
            return self.DEFAULT_BASE_URL

    @staticmethod
    def _local_path() -> str:
        return os.path.join(os.getcwd(), "wandb", "settings")

    @staticmethod
    def _global_path() -> str:
        default_config_dir = os.path.join(os.path.expanduser("~"), ".config", "wandb")
        config_dir = os.environ.get("WANDB_CONFIG_DIR", default_config_dir)
        return os.path.join(config_dir, "settings")


def get_weave_parallelism() -> int:
    return int(os.getenv(WEAVE_PARALLELISM, "20"))


def wandb_base_url() -> str:
    settings = Settings()
    return os.environ.get("WANDB_BASE_URL", settings.base_url).rstrip("/")


def wandb_frontend_base_url() -> str:
    public_url = os.getenv("WANDB_PUBLIC_BASE_URL", "").rstrip("/")
    if public_url:
        return public_url
    # Import here to avoid circular dependency
    from weave.compat import wandb

    # Transform API URL to frontend URL (e.g., https://api.wandb.ai -> https://wandb.ai)
    return wandb.app_url(wandb_base_url())


def weave_trace_server_url() -> str:
    """Get the full URL for the trace server API endpoints."""
    base_url = wandb_frontend_base_url()
    default = "https://trace.wandb.ai"
    # Check if we're not using the default cloud frontend URL
    if base_url != "https://wandb.ai":
        default = base_url + "/traces"
    return os.getenv("WF_TRACE_SERVER_URL", default)


def weave_frontend_url() -> str:
    """Get the frontend URL for UI navigation.

    This respects the WF_TRACE_SERVER_URL environment variable for custom deployments.
    When WF_TRACE_SERVER_URL is set, extracts the base URL (scheme + host + port) from it.

    Returns:
        The base URL to use for frontend navigation
    """
    trace_server_url = os.getenv("WF_TRACE_SERVER_URL")

    if trace_server_url:
        # Parse the URL to extract scheme, host, and port
        try:
            parsed = urlparse(trace_server_url)
            if parsed.scheme and parsed.netloc:
                # Build base URL from scheme and netloc (host:port)
                return f"{parsed.scheme}://{parsed.netloc}"
            else:
                # Invalid URL, fall back to localhost
                return "http://localhost:9000"
        except Exception:
            # If parsing fails, fall back to localhost
            return "http://localhost:9000"
    else:
        # Use the default frontend base URL
        return wandb_frontend_base_url()


def _wandb_api_key_via_env() -> str | None:
    api_key = os.environ.get("WANDB_API_KEY")
    return api_key


def _wandb_api_key_via_netrc() -> str | None:
    for filepath in ("~/.netrc", "~/_netrc"):
        api_key = _wandb_api_key_via_netrc_file(filepath)
        if api_key:
            return api_key
    return None


def _wandb_api_key_via_netrc_file(filepath: str) -> str | None:
    netrc_path = os.path.expanduser(filepath)
    if not os.path.exists(netrc_path):
        return None
    nrc = netrc.netrc(netrc_path)
    res = nrc.authenticators(urlparse(wandb_base_url()).netloc)
    api_key = None
    if res:
        _, _, api_key = res
    return api_key


def weave_wandb_api_key() -> str | None:
    env_api_key = _wandb_api_key_via_env()
    if env_api_key is not None:
        return env_api_key

    return _wandb_api_key_via_netrc()
