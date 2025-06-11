"""
This is a temporary patch for wandb in order to implement basic referrer tracking in
auth URLs. This commit: https://github.com/wandb/wandb/commit/5db4d763516ba2a3e8d94a85ba67bdf6fc124423
adds a utility for referrer tracking, but is not yet released. Once released, this patch
can be removed and instead https://github.com/wandb/weave/pull/4004/files can be merged.

Since this will take more than a month, we need a short-term patch to ensure that we can
start to track referrers.
"""

import inspect
from functools import wraps
from typing import Any

wandb: Any | None
try:
    import wandb as wandb_module  # type: ignore

    wandb = wandb_module
except ImportError:  # pragma: no cover - wandb optional
    wandb = None

wandb_termlog: Any | None = wandb.termlog if wandb is not None else None
patched = False


@wraps(wandb_termlog)  # type: ignore[arg-type]
def unsafe_termlog(*args: Any, **kwargs: Any) -> None:
    """
    Appends a `?ref=weave` to the end of the string if it ends with `/authorize`.
    This is used deep in the auth flow in wandb and allows us to determine that
    signups are coming from weave.
    """
    if wandb_termlog is None:
        return
    bound_args = inspect.signature(wandb_termlog).bind(*args, **kwargs)
    bound_args.apply_defaults()
    if string_arg_val := bound_args.arguments.get("string"):
        if isinstance(string_arg_val, str):
            if (
                string_arg_val.startswith(
                    "You can find your API key in your browser here:"
                )
                and "http" in string_arg_val
                and string_arg_val.endswith("/authorize")
            ):
                string_arg_val = string_arg_val + "?ref=weave"
    bound_args.arguments["string"] = string_arg_val
    return wandb_termlog(**bound_args.arguments) if wandb_termlog is not None else None


@wraps(wandb_termlog)  # type: ignore[arg-type]
def safe_termlog(*args: Any, **kwargs: Any) -> None:
    try:
        return unsafe_termlog(*args, **kwargs)
    except Exception as e:
        if wandb_termlog is not None:
            return wandb_termlog(*args, **kwargs)
        return None


def ensure_patched() -> None:
    global patched
    if patched or wandb is None or wandb_termlog is None:
        return
    wandb.termlog = safe_termlog
    patched = True


def ensure_unpatched() -> None:
    global patched
    if not patched or wandb is None or wandb_termlog is None:
        return
    wandb.termlog = wandb_termlog
    patched = False
