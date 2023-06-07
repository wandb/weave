from weave import context_state
import logging

logging.getLogger("langchain").setLevel(logging.ERROR)

loading_builtins_token = context_state.set_loading_built_ins()

try:
    from .lc import *
finally:
    context_state.clear_loading_built_ins(loading_builtins_token)
