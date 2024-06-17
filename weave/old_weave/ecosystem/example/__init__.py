# We need this boilerplate for all ecosystem packages for now.

import logging

from weave.old_weave import context_state

logging.getLogger("ecosystem_example").setLevel(logging.ERROR)

loading_builtins_token = context_state.set_loading_built_ins()

try:
    from weave.old_weave.ecosystem.example import ops
finally:
    context_state.clear_loading_built_ins(loading_builtins_token)
