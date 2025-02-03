# We need this boilerplate for all ecosystem packages for now.

import logging

from weave_query import context_state

logging.getLogger("ecosystem_example").setLevel(logging.ERROR)

loading_builtins_token = context_state.set_loading_built_ins()

try:
    from weave_query.ecosystem.hdbscan.ops import *
finally:
    context_state.clear_loading_built_ins(loading_builtins_token)
