import logging

from weave.legacy.weave import context_state

logging.getLogger("langchain").setLevel(logging.ERROR)

loading_builtins_token = context_state.set_loading_built_ins()

try:
    from weave.legacy.weave.ecosystem.langchain.lc import *
finally:
    context_state.clear_loading_built_ins(loading_builtins_token)
