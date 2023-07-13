from __future__ import annotations
from typing_extensions import (
    NotRequired,
    TypedDict,
)
import warnings
import threading
import typing
import weave
import pyarrow as pa


from ... import ops_arrow

UMAP_LIB = None

UMAP_LOCK = threading.Lock()


def get_umap():
    # Lazily load a cached version of UMAP - umap import
    # time is quite expensive so we want to do it once and
    # only when needed
    global UMAP_LIB
    if UMAP_LIB is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            import umap

            UMAP_LIB = umap
    return UMAP_LIB


class UMAPOptions(TypedDict):
    n_neighbors: NotRequired[int]
    min_dist: NotRequired[float]
    n_components: NotRequired[int]
    random_state: NotRequired[int]


@weave.op()
def umap_project(
    data: list[list[float]], options: typing.Optional[UMAPOptions]
) -> ops_arrow.ArrowWeaveList[list[float]]:
    if options == None:
        options = {}  # type: ignore
    model = get_umap().UMAP(**options)
    with UMAP_LOCK:
        umap_res = model.fit_transform(data)
    arrow_res = pa.array([a for a in umap_res])

    return ops_arrow.ArrowWeaveList(arrow_res)
