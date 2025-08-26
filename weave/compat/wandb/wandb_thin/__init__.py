"""A minimal reimplementation of a subset of the wandb library required for weave."""

from weave.compat.wandb.wandb_thin import env
from weave.compat.wandb.wandb_thin.internal_api import Api, ApiAsync
from weave.compat.wandb.wandb_thin.login import login
from weave.compat.wandb.wandb_thin.termlog import termerror, termlog, termwarn

__all__ = [
    "Api",
    "ApiAsync",
    "env",
    "login",
    "termerror",
    "termlog",
    "termwarn",
]
