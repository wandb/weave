from weave import context_state

loading_builtins_token = context_state.set_loading_built_ins()

try:
    from .rep import *
finally:
    context_state.clear_loading_built_ins(loading_builtins_token)
