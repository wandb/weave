"""The top-level functions and classes for working with Weave."""

import sys

# We track what modules were loaded before importing weave, so we can ensure
# that someone doesn't introduce auto-importing loading weave.legacy.weave.ops or weave.legacy.weave.panels
# (because they are slow to import and have more dependencies, and they are part of
# the engine and UI layers which should be kept separate from the core layer).
pre_init_modules = set(sys.modules.keys())

from weave.legacy.weave import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()

from weave.legacy.weave import weave_types as types
from weave.legacy.weave import storage
from weave.legacy.weave.api import *
from weave.legacy.weave.errors import *
from weave.legacy.weave import mappers_python_def
from weave.legacy.weave import wandb_api as _wandb_api
from weave.legacy.weave import context as _context

from weave import version

_wandb_api.init()

# Ensure there is a client available for eager mode


from weave.trace.api import *
_context_state.clear_loading_built_ins(_loading_builtins_token)

__version__ = version.VERSION

from weave.flow.obj import Object
from weave.flow.dataset import Dataset
from weave.flow.model import Model
from weave.flow.eval import Evaluation, Scorer
from weave.flow.agent import Agent, AgentState
from weave.trace.util import ThreadPoolExecutor, Thread

# See the comment above pre_init_modules above. This is check to ensure we don't accidentally
# introduce loading weave.legacy.weave.ops or weave.legacy.weave.panels when importing weave.
newly_added_modules = set(sys.modules.keys()) - pre_init_modules
ops_modules = []
panels_modules = []
for module_name in newly_added_modules:
    if module_name.startswith("weave.legacy.weave.ops"):
        ops_modules.append(module_name)
    if module_name.startswith("weave.legacy.weave.panels"):
        panels_modules.append(module_name)
if ops_modules or panels_modules:
    all_invalid_modules = ops_modules + panels_modules
    invalid_submodules = set([".".join(m.split(".")[:2]) for m in all_invalid_modules])
    raise errors.WeaveInternalError(
        "importing weave should not import weave.legacy.weave.ops or weave.legacy.weave.panels, but the following modules were imported: "
        + ", ".join(invalid_submodules)
    )

# Special object informing doc generation tooling which symbols
# to document & to associate with this module.
__docspec__ = [
    # Re-exported from trace.api
    init,
    publish,
    ref,
    get_current_call,
    finish,
    op,
    # Re-exported from flow module
    Object,
    Dataset,
    Model,
    Evaluation,
    Scorer,
]
