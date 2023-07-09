import typing
import weave
import numpy as np

import pyarrow as pa
import pyarrow.compute as pc

from ... import ops_arrow

import hdbscan


class HDBSCANOptions(typing.TypedDict):
    min_samples: typing.Optional[int]
    min_cluster_size: typing.Optional[int]


@weave.op()
def hdbscan_cluster(
    data: list[list[float]], options: typing.Optional[HDBSCANOptions]
) -> ops_arrow.ArrowWeaveList[typing.Optional[str]]:
    if options == None:
        options = {}  # type: ignore
    np_arr = hdbscan.HDBSCAN(**options).fit_predict(data)

    arr = pa.array(np_arr)
    item_is_null = pa.compute.equal(arr, pa.scalar(-1))
    result = pa.compute.replace_with_mask(
        arr, item_is_null, pa.scalar(None, pa.int64())
    )
    str_result = result.cast(pa.string())

    return ops_arrow.ArrowWeaveList(str_result)
