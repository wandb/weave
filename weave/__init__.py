import sys

# We track what modules were loaded before importing weave, so we can ensure
# that someone doesn't introduce auto-importing loading weave.ops or weave.panels
# (because they are slow to import and have more dependencies, and they are part of
# the engine and UI layers which should be kept separate from the core layer).
pre_init_modules = set(sys.modules.keys())

from . import context_state as _context_state
from . import logs as _logging

_loading_builtins_token = _context_state.set_loading_built_ins()

from . import weave_types as types
from . import storage

# this patches the `Type` class to enable the make method - needed due to circular references
# from . import make_type as _make_type
# from . import ops
# from . import codify
# from .graph import Node  # used as a type in op definitions
# from .show import show, show_url
from .api import *

# from . import panels
# from .panel import Panel

from .errors import *

from . import mappers_python_def

# TODO: Don't expose
# from .panel_util import make_node

from . import wandb_api as _wandb_api

# from .core_types import *
# from .monitoring import *

# from .panels_py import *
from . import version

# from . import ops_arrow as _ops_arrow

# WeaveList = _ops_arrow.ArrowWeaveList

_wandb_api.init()

# Ensure there is a client available for eager mode
from . import context as _context

# _context.get_client()
# Eager by default
# _context_state._eager_mode.set(True)

_context_state.clear_loading_built_ins(_loading_builtins_token)

# Wow, this works! you can do just "weave" in a notebook and render
# something. Maybe render ecosystem panel?
# from .ecosystem import ecosystem


# def _ipython_display_():
#     return show(ecosystem())

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
