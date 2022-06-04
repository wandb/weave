def tracer():
    from ddtrace import tracer as ddtrace_tracer

    return ddtrace_tracer
