from weave_query.weave_query import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()

from weave_query.weave_query.panels_py import (
    generator_templates as generator_templates,
)
from weave_query.weave_query.panels_py import (
    panel_autoboard as panel_autoboard,
)
from weave_query.weave_query.panels_py import (
    panel_llm_monitor as panel_llm_monitor,
)
from weave_query.weave_query.panels_py import (
    panel_observability as panel_observability,
)
from weave_query.weave_query.panels_py import (
    panel_seedboard as panel_seedboard,
)
from weave_query.weave_query.panels_py import (
    panel_trace_monitor as panel_trace_monitor,
)

# This is just an example, uncomment to enable
# from weave_query.weave_query.panels_py import panel_example_custom_board

_context_state.clear_loading_built_ins(_loading_builtins_token)
