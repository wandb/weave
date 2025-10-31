"""Compatibility layer for wandb.

This allows weave to work even if the wandb library is not installed.  If wandb
is available, we use that.  Otherwise, we reimplement a minimal subset of the
wandb API required by weave.
"""

# mypy: disable-error-code="assignment"

try:
    WANDB_AVAILABLE = True
    from wandb import env, login, termerror, termlog, termwarn, util
    from wandb.errors import AuthenticationError, CommError
    from wandb.sdk.internal.internal_api import logger as wandb_logger
    from wandb.util import app_url
except (ImportError, ModuleNotFoundError):
    WANDB_AVAILABLE = False
    from weave.compat.wandb.wandb_thin import (  # type: ignore[no-redef]
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

from weave.compat.wandb.wandb_thin import Api, ApiAsync

__all__ = [
    "WANDB_AVAILABLE",
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
