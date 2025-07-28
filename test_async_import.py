#!/usr/bin/env python3

try:
    from weave.trace_server.async_external_to_internal_trace_server_adapter import AsyncExternalTraceServer
    from weave.trace_server.external_to_internal_trace_server_adapter import IdConverter
    print("✅ Import successful! AsyncExternalTraceServer and IdConverter are available.")
    print(f"AsyncExternalTraceServer: {AsyncExternalTraceServer}")
    print(f"IdConverter: {IdConverter}")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc() 