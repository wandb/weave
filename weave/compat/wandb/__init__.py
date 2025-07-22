try:
    WANDB_AVAILABLE = True
    from wandb import login, termerror, termlog, termwarn
    from wandb.errors import AuthenticationError, CommError
    from wandb.sdk.internal.internal_api import logger as wandb_logger
    from wandb.util import app_url
except (ImportError, ModuleNotFoundError):
    WANDB_AVAILABLE = False
    from weave.compat.wandb.wandb_thin import (  # type: ignore[assignment]
        login,
        termerror,
        termlog,
        termwarn,
    )
    from weave.compat.wandb.wandb_thin.errors import (  # type: ignore[assignment]
        AuthenticationError,
        CommError,
    )
    from weave.compat.wandb.wandb_thin.internal_api import (
        logger as wandb_logger,  # type: ignore[assignment]
    )
    from weave.compat.wandb.wandb_thin.util import app_url  # type: ignore[assignment]

from weave.compat.wandb.wandb_thin import Api, ApiAsync

__all__ = [
    "WANDB_AVAILABLE",
    "Api",
    "ApiAsync",
    "AuthenticationError",
    "CommError",
    "app_url",
    "login",
    "termerror",
    "termlog",
    "termwarn",
    "wandb_logger",
]
