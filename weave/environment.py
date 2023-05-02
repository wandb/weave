"""Environment variables used by weave."""

# TODO: we should put all other env vars here to keep them organized.

import enum
import os
import pathlib
import typing
from . import util
from . import errors
from urllib.parse import urlparse
import netrc

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


def weave_server_url() -> str:
    return os.getenv("WEAVE_SERVER_URL", "")


def wandb_base_url() -> str:
    return os.environ.get("WANDB_BASE_URL", "https://api.wandb.ai")


def weave_filesystem_dir() -> str:
    # WEAVE_LOCAL_ARTIFACT_DIR should be renamed to WEAVE_FILESYSTEM_DIR
    # TODO
    return os.environ.get("WEAVE_LOCAL_ARTIFACT_DIR") or os.path.join(
        "/tmp", "weave", "fs"
    )


def enable_touch_on_read() -> bool:
    return util.parse_boolean_env_var("WEAVE_ENABLE_TOUCH_ON_READ")


def weave_wandb_cookie() -> typing.Optional[str]:
    cookie = os.environ.get("WEAVE_WANDB_COOKIE")
    if cookie:
        if is_public():
            raise errors.WeaveConfigurationError(
                "WEAVE_WANDB_COOKIE should not be set in public mode."
            )
        if os.path.exists(os.path.expanduser("~/.netrc")):
            raise errors.WeaveConfigurationError(
                "Please delete ~/.netrc while using WEAVE_WANDB_COOKIE to avoid using your credentials"
            )
    return cookie


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
