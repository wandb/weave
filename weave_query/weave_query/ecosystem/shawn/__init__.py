from weave_query.weave_query import context_state as _context

_loading_builtins_token = _context.set_loading_built_ins()

from weave_query.weave_query.ecosystem.shawn import petdataset as petdataset
from weave_query.weave_query.ecosystem.shawn import scratch as scratch

_context.clear_loading_built_ins(_loading_builtins_token)
