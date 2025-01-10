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
    return public_url if public_url != "" else wandb_base_url()


def weave_trace_server_url() -> str:
    base_url = wandb_frontend_base_url()
    default = "https://trace.wandb.ai"
    if base_url != "https://api.wandb.ai":
        default = base_url + "/traces"
    return os.getenv("WF_TRACE_SERVER_URL", default)


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
    netrc_api_key = _wandb_api_key_via_netrc()
    if env_api_key and netrc_api_key and env_api_key != netrc_api_key:
        logger.warning(
            "There are different credentials in the netrc file and the environment. Using the environment value."
        )
    return env_api_key or netrc_api_key
