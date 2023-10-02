"""Environment variables used by weave."""

# TODO: we should put all other env vars here to keep them organized.

import configparser
import enum
import os
import pathlib
import typing
from . import util
from . import errors
from urllib.parse import urlparse
import netrc
from distutils.util import strtobool

if typing.TYPE_CHECKING:
    from . import logs

WANDB_ERROR_REPORTING = "WANDB_ERROR_REPORTING"
WEAVE_USAGE_ANALYTICS = "WEAVE_USAGE_ANALYTICS"
WEAVE_GQL_SCHEMA_PATH = "WEAVE_GQL_SCHEMA_PATH"


def _env_as_bool(var: str, default: typing.Optional[str] = None) -> bool:
    env = os.environ
    val = env.get(var, default)
    try:
        val = bool(strtobool(val))  # type: ignore
    except (AttributeError, ValueError):
        pass
    return val if isinstance(val, bool) else False


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


# There are currently two cache modes:
# - full: cache all cacheable intermediate results
# - minimal: cache only what we're sure we need to cache for performance
# WEAVE_NO_CACHE indicates that we're using the minimal cache mode. Otherwise
# we'll use full.
class CacheMode(enum.Enum):
    FULL = "full"
    MINIMAL = "minimal"


def cache_mode() -> CacheMode:
    if util.parse_boolean_env_var("WEAVE_NO_CACHE"):
        return CacheMode.MINIMAL
    env_mode = os.getenv("WEAVE_CACHE_MODE", CacheMode.MINIMAL.value)
    for mode in CacheMode:
        if mode.value == env_mode:
            return mode
    raise errors.WeaveConfigurationError(
        f"WEAVE_CACHE_MODE must be one of {list(CacheMode)}"
    )


def wandb_production() -> bool:
    return os.getenv("WEAVE_ENV") == "wandb_production"


def is_public() -> bool:
    return wandb_production()


def weave_log_format(default: "logs.LogFormat") -> "logs.LogFormat":
    from .logs import LogFormat

    return LogFormat(os.getenv("WEAVE_LOG_FORMAT", default))


def weave_link_prefix() -> str:
    """When running in server we mount index under /weave"""
    if os.getenv("GORILLA_ONPREM") == "true":
        return "/weave"
    return ""


def weave_onprem() -> bool:
    return os.getenv("GORILLA_ONPREM") == "true"


def weave_backend_host() -> str:
    return os.getenv("WEAVE_BACKEND_HOST", "/__weave")


def analytics_disabled() -> bool:
    if os.getenv("WEAVE_DISABLE_ANALYTICS") == "true":
        return True
    return False


def weave_server_url() -> str:
    base_url = wandb_base_url()
    default = "https://weave.wandb.ai"
    if base_url != "https://api.wandb.ai":
        default = base_url + "/weave"
    return os.getenv("WEAVE_SERVER_URL", default)


def wandb_base_url() -> str:
    settings = Settings()
    return os.environ.get("WANDB_BASE_URL", settings.base_url).rstrip("/")


def weave_filesystem_dir() -> str:
    # WEAVE_LOCAL_ARTIFACT_DIR should be renamed to WEAVE_FILESYSTEM_DIR
    # TODO
    return os.environ.get("WEAVE_LOCAL_ARTIFACT_DIR") or os.path.join(
        "/tmp", "weave", "fs"
    )


def enable_touch_on_read() -> bool:
    return util.parse_boolean_env_var("WEAVE_ENABLE_TOUCH_ON_READ")


def memdump_sighandler_enabled() -> bool:
    return util.parse_boolean_env_var("WEAVE_ENABLE_MEMDUMP_SIGHANDLER")


def sigterm_sighandler_enabled() -> bool:
    return util.parse_boolean_env_var("WEAVE_ENABLE_SIGTERM_SIGHANDLER")


def weave_wandb_cookie() -> typing.Optional[str]:
    cookie = os.environ.get("WEAVE_WANDB_COOKIE")
    if cookie:
        if is_public():
            raise errors.WeaveConfigurationError(
                "WEAVE_WANDB_COOKIE should not be set in public mode."
            )
        for netrc_file in ("~/.netrc", "~/_netrc"):
            if os.path.exists(os.path.expanduser(netrc_file)):
                raise errors.WeaveConfigurationError(
                    f"Please delete {netrc_file} while using WEAVE_WANDB_COOKIE to avoid using your credentials"
                )
    return cookie


def stack_dump_sighandler_enabled() -> bool:
    return util.parse_boolean_env_var("WEAVE_ENABLE_STACK_DUMP_SIGHANDLER")


def _wandb_api_key_via_env() -> typing.Optional[str]:
    api_key = os.environ.get("WANDB_API_KEY")
    if api_key and is_public():
        raise errors.WeaveConfigurationError(
            "WANDB_API_KEY should not be set in public mode."
        )
    return api_key


def _wandb_api_key_via_netrc() -> typing.Optional[str]:
    netrc_path = os.path.expanduser("~/.netrc")
    if not os.path.exists(netrc_path):
        return None
    nrc = netrc.netrc(netrc_path)
    res = nrc.authenticators(urlparse(wandb_base_url()).netloc)
    api_key = None
    if res:
        user, account, api_key = res
    if api_key and is_public():
        raise errors.WeaveConfigurationError(
            "~/.netrc should not be set in public mode."
        )
    return api_key


def weave_wandb_api_key() -> typing.Optional[str]:
    env_api_key = _wandb_api_key_via_env()
    netrc_api_key = _wandb_api_key_via_netrc()
    if env_api_key and netrc_api_key:
        raise errors.WeaveConfigurationError(
            "WANDB_API_KEY should not be set in both ~/.netrc and the environment."
        )
    return env_api_key or netrc_api_key


def projection_timeout_sec() -> typing.Optional[typing.Union[int, float]]:
    return util.parse_number_env_var("WEAVE_PROJECTION_TIMEOUT_SEC")


def num_gql_timeout_retries() -> int:
    raw = util.parse_number_env_var("WEAVE_WANDB_GQL_NUM_TIMEOUT_RETRIES")
    if raw is None:
        return 0
    return int(raw)


def usage_analytics_enabled() -> bool:
    return _env_as_bool(WANDB_ERROR_REPORTING, default="True") and _env_as_bool(
        WEAVE_USAGE_ANALYTICS, default="True"
    )


def gql_schema_path() -> typing.Optional[str]:
    return os.environ.get(WEAVE_GQL_SCHEMA_PATH) or None
