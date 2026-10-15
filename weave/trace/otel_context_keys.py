"""OTel context keys that the Weave client SDK and the trace server agree on.

The trace server in wandb/core has its own copy of this module, so a key is a
fixed string rather than `otel_context.create_key`, which mints a new unique
string on every call.
"""

# Holds the innermost `weave.trace_server` span while it is current, so the
# client SDK can tell one of our own server spans from an agent's. It stores the
# span rather than a flag because an agent span opened inside a server frame —
# a hosted evaluation running an agent — is a legitimate link target, and only
# an identity comparison distinguishes the two. Inspecting the span object alone
# would not work: under the OTel→DD bridge it is not an SDK span and carries no
# instrumentation scope.
WEAVE_SERVER_SPAN_KEY = "weave.trace_server.span"
