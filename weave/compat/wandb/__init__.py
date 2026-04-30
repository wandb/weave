"""Compatibility layer that re-exports the minimal wandb-like surface weave needs.

Previously this layer preferred the real `wandb` package when available and
fell back to a vendored shim.  It now always uses `wandb_thin` so weave runs
without any `wandb` dependency installed.
"""

from weave.compat.wandb.wandb_thin import (
    Api,
    ApiAsync,
    env,
    login,
    termerror,
    termlog,
    termwarn,
    util,
)
from weave.compat.wandb.wandb_thin.errors import AuthenticationError, CommError
from weave.compat.wandb.wandb_thin.internal_api import logger as wandb_logger
from weave.compat.wandb.wandb_thin.util import app_url

__all__ = [
    "Api",
    "ApiAsync",
    "AuthenticationError",
    "CommError",
    "app_url",
    "env",
    "login",
    "termerror",
    "termlog",
    "termwarn",
    "util",
    "wandb_logger",
]
