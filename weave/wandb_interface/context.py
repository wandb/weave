from __future__ import annotations

import contextvars

from weave.trace.env import weave_wandb_api_key

# When set, overrides env-based API key lookup. This allows weave.init(api_key=...)
# to propagate the explicit key to all downstream code (e.g. entity resolution)
# without touching environment variables.
_explicit_api_key: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_explicit_api_key", default=None
)


def set_wandb_api_context(api_key: str | None) -> None:
    """Set an explicit API key that overrides env-based lookup."""
    _explicit_api_key.set(api_key)


def get_wandb_api_context() -> str | None:
    """Return the current W&B API key.

    Checks explicit override first, then falls back to env var / netrc.
    """
    explicit = _explicit_api_key.get()
    if explicit is not None:
        return explicit
    return weave_wandb_api_key()
