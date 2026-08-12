"""OTel context keys shared between the Weave client SDK and the trace server.

`otel_context.create_key` mints a fresh unique string on every call, so a key
both sides must agree on has to be created exactly once, in a module both are
allowed to import.
"""

from opentelemetry import context as otel_context

# Holds the innermost `weave.trace_server` span while it is current, so the
# client SDK can tell one of our own server spans from an agent's. It stores the
# span rather than a flag because an agent span opened inside a server frame —
# a hosted evaluation running an agent — is a legitimate link target, and only
# an identity comparison distinguishes the two. Inspecting the span object alone
# would not work: under the OTel→DD bridge it is not an SDK span and carries no
# instrumentation scope.
WEAVE_SERVER_SPAN_KEY = otel_context.create_key("weave.trace_server.span")
