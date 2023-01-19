"""Environment variables used by weave."""

# TODO: we should put all other env vars here to keep them organized.

import enum
import os
import typing
from . import util

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
    else:
        return CacheMode.FULL


def wandb_production() -> bool:
    return os.getenv("WEAVE_ENV") == "wandb_production"


def weave_server_url() -> str:
    return os.getenv("WEAVE_SERVER_URL", "")
