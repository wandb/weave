# We need this boilerplate for all ecosystem packages for now.

from weave import context_state
import logging

logging.getLogger("ecosystem_example").setLevel(logging.ERROR)

loading_builtins_token = context_state.set_loading_built_ins()

try:
    from . import ops
finally:
    context_state.clear_loading_built_ins(loading_builtins_token)
