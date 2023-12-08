from . import context_state as _context_state
from . import logs as _logging

_loading_builtins_token = _context_state.set_loading_built_ins()

from . import weave_types as types
from . import storage

# this patches the `Type` class to enable the make method - needed due to circular references
from . import make_type as _make_type
from . import ops
from . import codify
from .graph import Node  # used as a type in op definitions
from .show import show, show_url
from .api import *

from . import panels
from .panel import Panel

from .errors import *

# TODO: Don't expose
from .panel_util import make_node

from . import wandb_api as _wandb_api

from .core_types import *
from .monitoring import *

from .panels_py import *
from . import version

from . import ops_arrow as _ops_arrow

WeaveList = _ops_arrow.ArrowWeaveList

_wandb_api.init()

# Ensure there is a client available for eager mode
from . import context as _context

_context.get_client()
# Eager by default
# _context_state._eager_mode.set(True)

_context_state.clear_loading_built_ins(_loading_builtins_token)

# Wow, this works! you can do just "weave" in a notebook and render
# something. Maybe render ecosystem panel?
# from .ecosystem import ecosystem


# def _ipython_display_():
#     return show(ecosystem())

__version__ = version.VERSION
