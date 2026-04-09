from __future__ import annotations

from weave.trace.env import weave_wandb_api_key

# When set, overrides env-based API key lookup. This allows weave.init(api_key=...)
# to propagate the explicit key to all downstream code (e.g. entity resolution)
# without touching environment variables. Uses a plain global (not contextvars)
# because this value must be visible across threads.
_explicit_api_key: str | None = None


def set_wandb_api_context(api_key: str | None) -> None:
    """Set an explicit API key that overrides env-based lookup."""
    global _explicit_api_key  # noqa: PLW0603
    _explicit_api_key = api_key


def get_wandb_api_context() -> str | None:
    """Return the current W&B API key.

    Checks explicit override first, then falls back to env var / netrc.
    """
    if _explicit_api_key is not None:
        return _explicit_api_key
    return weave_wandb_api_key()
