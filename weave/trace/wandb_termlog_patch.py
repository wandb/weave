"""
This is a temporary patch for wandb in order to implement basic referrer tracking in
auth URLs. This commit: https://github.com/wandb/wandb/commit/5db4d763516ba2a3e8d94a85ba67bdf6fc124423 
adds a utility for refferer tracking, but is not yet released. Once released, this patch
can be removed and instead https://github.com/wandb/weave/pull/4004/files can be merged.

Since this will take more than a month, we need a short-term patch to ensure that we can
start to track referrers.
"""

import inspect
from functools import wraps

import wandb

original_termlog = None

@wraps(wandb.termlog)
def unsafe_termlog(*args, **kwargs):
    bound_args = inspect.signature(wandb.termlog).bind(*args, **kwargs)
    bound_args.apply_defaults()
    if string_arg_val := bound_args.arguments.get("string"):
        if isinstance(string_arg_val, str):
            if string_arg_val.endswith("/authorize"):
                string_arg_val = string_arg_val + "?ref=weave"
    bound_args.arguments["string"] = string_arg_val
    return wandb.termlog(**bound_args.arguments)

@wraps(wandb.termlog)
def safe_termlog(*args, **kwargs):
    try:
        return unsafe_termlog(*args, **kwargs)
    except Exception as e:
        return wandb.termlog(*args, **kwargs)


def ensure_patched():
    global original_termlog
    if original_termlog:
        return
    original_termlog = wandb.termlog
    wandb.termlog = safe_termlog


def ensure_unpatched():
    global original_termlog
    if not original_termlog:
        return
    wandb.termlog = original_termlog
    original_termlog = None
