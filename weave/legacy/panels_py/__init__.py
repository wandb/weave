from weave.legacy import context_state as _context_state

_loading_builtins_token = _context_state.set_loading_built_ins()

from weave.legacy.panels_py import (
    generator_templates,
    panel_autoboard,
    panel_llm_monitor,
    panel_observability,
    panel_seedboard,
    panel_trace_monitor,
)

# This is just an example, uncomment to enable
# from weave.legacy.panels_py import panel_example_custom_board

_context_state.clear_loading_built_ins(_loading_builtins_token)
