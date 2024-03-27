import os

WEAVE_PARALLELISM = "WEAVE_PARALLELISM"


def get_weave_parallelism():
    return int(os.getenv(WEAVE_PARALLELISM, "20"))
