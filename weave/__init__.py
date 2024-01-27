import sys

# We track what modules were loaded before importing weave, so we can ensure
# that someone doesn't introduce auto-importing loading weave.ops or weave.panels
# (because they are slow to import and have more dependencies, and they are part of
# the engine and UI layers which should be kept separate from the core layer).
pre_init_modules = set(sys.modules.keys())

from . import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()

from . import weave_types as types
from . import storage

from .api import *


from .errors import *

from . import mappers_python_def

from . import wandb_api as _wandb_api

from . import version

_wandb_api.init()

# Ensure there is a client available for eager mode
from . import context as _context

_context_state.clear_loading_built_ins(_loading_builtins_token)

__version__ = version.VERSION


# See the comment above pre_init_modules above. This is check to ensure we don't accidentally
# introduce loading weave.ops or weave.panels when importing weave.
newly_added_modules = set(sys.modules.keys()) - pre_init_modules
ops_modules = []
panels_modules = []
for module_name in newly_added_modules:
    if module_name.startswith("weave.ops"):
        ops_modules.append(module_name)
    if module_name.startswith("weave.panels"):
        panels_modules.append(module_name)
if ops_modules or panels_modules:
    all_invalid_modules = ops_modules + panels_modules
    invalid_submodules = set([".".join(m.split(".")[:2]) for m in all_invalid_modules])
    raise errors.WeaveInternalError(
        "importing weave should not import weave.ops or weave.panels, but the following modules were imported: "
        + ", ".join(invalid_submodules)
    )
