from logging import getLogger

logger = getLogger("weave")

def weave_print(*args, **kwargs):
    should_print = True
    if not should_print:
        return
    print(*args, **kwargs)