import os
from typing import Optional

from distutils.util import strtobool


WANDB_ERROR_REPORTING = "WANDB_ERROR_REPORTING"
WEAVE_USAGE_ANALYTICS = "WEAVE_USAGE_ANALYTICS"


def _env_as_bool(var: str, default: Optional[str] = None) -> bool:
    env = os.environ
    val = env.get(var, default)
    try:
        val = bool(strtobool(val))  # type: ignore
    except (AttributeError, ValueError):
        pass
    return val if isinstance(val, bool) else False


def usage_analytics_enabled() -> bool:
    return _env_as_bool(WANDB_ERROR_REPORTING, default="True") and _env_as_bool(
        WEAVE_USAGE_ANALYTICS, default="True"
    )
