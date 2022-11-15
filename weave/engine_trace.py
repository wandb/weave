import os


class DummyTrace:
    def trace(self, *args, **kwargs):
        return None


def tracer():
    if os.getenv("DD_ENV"):
        from ddtrace import tracer as ddtrace_tracer

        return ddtrace_tracer
    else:
        return DummyTrace()
