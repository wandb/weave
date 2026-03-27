from __future__ import annotations

from weave.trace.env import weave_wandb_api_key


def get_wandb_api_context() -> str | None:
    """Return the current W&B API key, reading from env var or netrc."""
    return weave_wandb_api_key()
