from .. import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()

from . import panel_llm_monitor
from . import panel_trace_monitor
from . import panel_autoboard
from . import panel_seedboard
from . import panel_observability
from . import generator_templates

# This is just an example, uncomment to enable
# from . import panel_example_custom_board

_context_state.clear_loading_built_ins(_loading_builtins_token)
