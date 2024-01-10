import pyarrow as pa
from weave.ops_domain.run_history.run_history_v3_parquet_stream_optimized import _consolidate_matching_types_in_dense_union_array, _dedup_dense_union_array, _flatten_dense_union_array


def test_union_simple():
    union_arr = pa.UnionArray.from_dense(
        pa.array([0, 1, 2], type=pa.int8()),
        pa.array([0, 1, 2], type=pa.int32()),
        [pa.array([1, 2, 3]), pa.array([4, 5, 6]), pa.array([7, 8, 9])],
    )
    do_union_array_test(union_arr)

def test_union_hard():
    union_arr = pa.UnionArray.from_dense(
        pa.array([0, 1, 0, 1, 0, 1], type=pa.int8()),
        pa.array([0, 0, 1, 2, 1, 2], type=pa.int32()),
        [pa.array([None, 1, None, 2]), pa.array([3, None, 4, None])],
    )
    union_arr = pa.UnionArray.from_dense(
        pa.array([0, 1, 0, 1, 0, 1], type=pa.int8()),
        pa.array([1, 2, 3, 0, 1, 2], type=pa.int32()),
        [union_arr, pa.array([5, 6, None, 7])],
    )
    do_union_array_test(union_arr)

def do_union_array_test(union_arr):
    flattened = _flatten_dense_union_array(union_arr)
    assert flattened.to_pylist() == union_arr.to_pylist()
    consolidated = _consolidate_matching_types_in_dense_union_array(flattened)
    assert consolidated.to_pylist() == union_arr.to_pylist()
    deduped = _dedup_dense_union_array(union_arr)
    assert deduped.to_pylist() == union_arr.to_pylist()
