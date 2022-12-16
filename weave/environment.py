"""Environment variables used by weave."""

# TODO: we should put all other env vars here to keep them organized.

import os
from . import util

# There are currently two cache modes:
# - full: cache all cacheable intermediate results
# - minimal: cache only what we're sure we need to cache for performance
# WEAVE_NO_CACHE indicates that we're using the minimal cache mode. Otherwise
# we'll use full.
def no_cache() -> bool:
    return util.parse_boolean_env_var("WEAVE_NO_CACHE")


def wandb_production() -> bool:
    return os.getenv("WEAVE_ENV") == "wandb_production"
