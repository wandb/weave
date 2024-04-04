import weave


@weave.op()
def track_me(v):
    return v + 5


weave.init("intro-example")
track_me(15)
