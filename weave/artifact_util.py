import os
from . import cache


def local_artifact_dir() -> str:
    # This is a directory that all local and wandb artifacts are stored within.
    # It includes the current cache namespace, which is a safe token per user,
    # to ensure cache separation.
    d = os.environ.get("WEAVE_LOCAL_ARTIFACT_DIR") or os.path.join(
        "/tmp", "local-artifacts"
    )
    cache_namespace = cache.get_user_cache_key()
    if cache_namespace:
        d = os.path.join(d, cache_namespace)
    os.makedirs(d, exist_ok=True)
    return d
