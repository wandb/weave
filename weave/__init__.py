from . import context_state as _context

_loading_builtins_token = _context.set_loading_built_ins()

from . import weave_types as types
from . import ops
from .graph import Node  # used as a type in op definitions
from .show import show, show_url
from .api import *

from . import panels
from .panel import Panel

# TODO: Don't expose
from .panel_util import make_node

_context.clear_loading_built_ins(_loading_builtins_token)

# Wow, this works! you can do just "weave" in a notebook and render
# something. Maybe render ecosystem panel?
# def _ipython_display_():
#     return show(ecosystem())
