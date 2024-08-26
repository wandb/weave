import os

WEAVE_PARALLELISM = "WEAVE_PARALLELISM"


def get_weave_parallelism() -> int:
    return int(os.getenv(WEAVE_PARALLELISM, "20"))


def wandb_production() -> bool:
    return os.getenv("WEAVE_ENV") == "wandb_production"
