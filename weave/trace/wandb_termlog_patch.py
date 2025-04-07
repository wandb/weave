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

wandb_termlog = wandb.termlog
patched = False

@wraps(wandb_termlog)
def unsafe_termlog(*args, **kwargs):
    bound_args = inspect.signature(wandb_termlog).bind(*args, **kwargs)
    bound_args.apply_defaults()
    if string_arg_val := bound_args.arguments.get("string"):
        if isinstance(string_arg_val, str):
            if string_arg_val.endswith("/authorize"):
                string_arg_val = string_arg_val + "?ref=weave"
    bound_args.arguments["string"] = string_arg_val
    return wandb_termlog(**bound_args.arguments)

@wraps(wandb_termlog)
def safe_termlog(*args, **kwargs):
    try:
        return unsafe_termlog(*args, **kwargs)
    except Exception as e:
        return wandb_termlog(*args, **kwargs)


def ensure_patched():
    global patched
    if patched:
        return
    wandb.termlog = safe_termlog
    patched = True

def ensure_unpatched():
    global patched
    if not patched:
        return
    wandb.termlog = wandb_termlog
    patched = False
