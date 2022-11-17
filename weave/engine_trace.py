import os


# Thanks co-pilot!
class DummySpan:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        pass

    def set_tag(self, *args, **kwargs):
        pass

    def set_meta(self, *args, **kwargs):
        pass

    def finish(self, *args, **kwargs):
        pass


class DummyTrace:
    def trace(self, *args, **kwargs):
        return DummySpan()


def tracer():
    if os.getenv("DD_ENV"):
        from ddtrace import tracer as ddtrace_tracer

        return ddtrace_tracer
    else:
        return DummyTrace()
