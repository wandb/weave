from . import weave_types as types
from . import ops
from . import panels
from .graph import Node  # used as a type in op definitions
from .show import show
from .api import *


# Experimenting with putting this at the top-level...
ecosystem = ops.ecosystem

# Wow, this works! you can do just "weave" in a notebook and render
# something. Maybe render ecosystem panel?
# def _ipython_display_():
#     return show(ops.ecosystem())
