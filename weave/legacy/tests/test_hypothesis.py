# Fuzz testing with the hypothesis library
#
# Quick summary: hypothesis is a fuzz testing framework. You
#   provide strategies for generating inputs, and assertions
#   for checking results. Hypothesis does a guided search
#   to look for bugs.
#
# Known Weave issues that we intentionally avoid here (but
# that will need to be fixed at some point):
# - Don't test large ints because we convert int64 to float64
#   in arrow sometimes, which truncates them.
# - We don't test float & int together in join2 because the Python
#   and arrow implementations differ in how they handle them.
#
# To debug and fix failing tests here:
# hypothesis will print output like this:
#   ValueError: ArrowWeaveList validation err: <UnknownType()>, null
#     Non-zero length array with UnknownType
#   Falsifying example: test_join2(
#       weave_no_cache=None,
#       list_lambda1=([0], lambda x: x),
#       list_lambda2=([], lambda x: x),
#       leftOuter=True,
#       rightOuter=False,
#   )
# This means that the test failed with the given inputs.
# You can force that specific example to run by adding
#   @example(
#       list_lambda1=([0], lambda x: x),
#       list_lambda2=([], lambda x: x),
#       leftOuter=True,
#       rightOuter=False,
#   )
# above the test function.

import dataclasses
import json
import os

import pyarrow as pa
import pytest
from hypothesis import example, given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite

import weave
from weave.legacy.weave import artifact_local, ops_arrow, ops_primitives, storage
from weave.legacy.weave.arrow import convert
from weave.legacy.weave.language_features.tagging import tag_store

# Jack this up to find more bugs.
EXAMPLES_PER_TEST = 100


@pytest.fixture(scope="module")
def weave_no_cache():
    old_cache = os.environ.get("WEAVE_NO_CACHE")
    os.environ["WEAVE_NO_CACHE"] = "1"
    yield
    if old_cache is None:
        del os.environ["WEAVE_NO_CACHE"]
    else:
        os.environ["WEAVE_NO_CACHE"] = old_cache


# MIN_INT64 = -(2**63)
# MAX_INT64 = 2**63 - 2  # why -2? If we use -1 we get an error

# We fail on union of large int and float, so don't use large ints for now
MIN_INT64 = -(2**32)
MAX_INT64 = 2**32


# make including float optional, because the behavior is different for
# arrow join v python join when both float and int and present. Rather
# than unifying, just disable the float case when doing join tests for now.
def obj_strategy(max_depth=3, include_float=True, include_none=True):
    basics = [
        st.integers(min_value=MIN_INT64, max_value=MAX_INT64),
        st.text(),
        st.booleans(),
    ]
    if include_float:
        basics.append(st.floats(allow_nan=False, allow_infinity=False))
    if include_none:
        basics.append(st.none())
    if max_depth <= 0:
        return st.one_of(*basics)
    else:
        return st.one_of(
            *basics,
            st.lists(
                obj_strategy(
                    max_depth - 1,
                    include_float=include_float,
                    include_none=include_none,
                ),
            ),
            st.dictionaries(
                st.sampled_from(["key", "foo", "bar"]),
                # Disable generating None values in dictionaries. Our arrow implementation
                # automatically adds Nones for missing keys in many cases. A known issue.
                obj_strategy(
                    max_depth - 1, include_float=include_float, include_none=False
                ),
                min_size=1,
                max_size=5,
            ),
        )


def list_strategy(max_depth=3, include_float=True):
    return st.lists(obj_strategy(max_depth, include_float))


def numeric_lambda_strategy():
    return st.sampled_from(
        [
            lambda x: x,
            lambda x: x * 2,
            lambda x: x - 1,
            lambda x: x + 1,
        ]
    )


@composite
def list_lambda_strategy(draw, include_float=True):
    l = draw(list_strategy(include_float=include_float))
    t = weave.type_of(l)
    ot = t.object_type
    if isinstance(ot, weave.types.TypedDict):
        return (l, lambda x: x["key"])
    elif isinstance(ot, weave.types.List):
        return (l, lambda x: x[0])
    elif isinstance(ot, weave.types.Number):
        return (l, draw(numeric_lambda_strategy()))
    else:
        return (l, lambda x: x)


def compare_py(val, orig):
    if isinstance(val, dict):
        assert isinstance(orig, dict)
        for k in orig:
            assert k in val
            compare_py(val[k], orig[k])
        for k in set(val) - set(orig):
            assert val[k] == None
    elif isinstance(val, list):
        assert isinstance(orig, list)
        assert len(val) == len(orig)
        for i in range(len(val)):
            compare_py(val[i], orig[i])
    else:
        assert val == orig


def fix_for_compare(x1):
    if isinstance(x1, list):
        return [fix_for_compare(x) for x in x1]
    elif isinstance(x1, dict):
        return {k: fix_for_compare(v) for k, v in x1.items()}
    elif dataclasses.is_dataclass(x1):
        return x1.__class__(
            **{k: fix_for_compare(v) for k, v in dataclasses.asdict(x1).items()}
        )
    elif isinstance(x1, artifact_local.LocalArtifact):
        return (x1.name, x1.version)
    return x1


@given(l1=st.lists(obj_strategy()))
@settings(max_examples=EXAMPLES_PER_TEST, deadline=None)
def test_to_from_arrow(l1):
    a1 = ops_arrow.to_arrow(l1)
    l1_result = a1.to_pylist_tagged()
    compare_py(l1_result, l1)


def rotate_list(l):
    if not l:
        return l
    return l[1:] + [l[0]]


def pa_equal_with_null(a1, a2):
    null_count = pa.compute.add(
        pa.compute.is_null(a1).cast(pa.int8()), pa.compute.is_null(a2).cast(pa.int8())
    )
    return pa.compute.if_else(
        pa.compute.equal(null_count, 2),
        pa.scalar(True),
        pa.compute.if_else(
            pa.compute.equal(null_count, 0), pa.compute.equal(a1, a2), pa.scalar(False)
        ),
    )


def compare_safe_equal(v1, v2):
    if isinstance(v1, dict):
        if not isinstance(v2, dict):
            return False
        for k in set(v1) | set(v2):
            if not compare_safe_equal(v1.get(k), v2.get(k)):
                return False
        return True
    elif isinstance(v1, list):
        if not isinstance(v2, list):
            return False
        if not len(v1) == len(v2):
            return False
        for i in range(len(v1)):
            if not compare_safe_equal(v1[i], v2[i]):
                return False
        return True
    elif isinstance(v1, bool):
        if not isinstance(v2, bool):
            return False
        return v1 == v2
    elif isinstance(v2, bool):
        if not isinstance(v1, bool):
            return False
        return v1 == v2
    elif isinstance(v1, (int, float)):
        if not isinstance(v2, (int, float)):
            return False
        return v1 == v2
    return v1 == v2


@given(l1=list_strategy())
@settings(max_examples=EXAMPLES_PER_TEST, deadline=None)
def test_to_compare_safe(l1):
    l2 = rotate_list(l1)
    a1 = ops_arrow.to_arrow(l1)
    a2 = ops_arrow.to_arrow(l2)
    safe1 = convert.to_compare_safe(a1)
    safe2 = convert.to_compare_safe(a2)
    safe1_arr = safe1._arrow_data
    safe2_arr = safe2._arrow_data
    # print("l1", l1)
    # print("l2", l2)
    # print("safe1_arr", safe1_arr)
    # print("safe2_arr", safe2_arr)
    if len(safe1_arr):
        # comparing to self is true!
        assert pa_equal_with_null(safe1_arr, safe1_arr).to_pylist() == [True] * len(
            safe1_arr
        )
    if len(safe2_arr):
        # comparing to self is true!
        assert pa_equal_with_null(safe2_arr, safe2_arr).to_pylist() == [True] * len(
            safe2_arr
        )
    if len(safe1_arr) and len(safe2_arr):
        assert pa_equal_with_null(safe1_arr, safe2_arr).to_pylist() == list(
            compare_safe_equal(i1, i2) for i1, i2 in zip(l1, l2)
        )


@given(l=st.lists(obj_strategy()))
@settings(max_examples=EXAMPLES_PER_TEST, deadline=None)
# @example(l=[None, {"foo": 0}, 0, {"foo": ""}])
@example(l=[None, {"foo": 15}, {"foo": "a"}])
def test_saveload(l, weave_no_cache):
    a = ops_arrow.to_arrow(l)
    a_ref = storage.save(a)
    a_again = storage.get(str(a_ref))
    assert a.object_type == a_again.object_type
    assert a._arrow_data == a_again._arrow_data


@given(l1=st.lists(obj_strategy()), l2=st.lists(obj_strategy()))
@settings(max_examples=EXAMPLES_PER_TEST, deadline=None)
def test_concat(l1, l2, weave_no_cache):
    a1 = ops_arrow.to_arrow(l1)
    l1_result = a1.to_pylist_tagged()
    compare_py(l1_result, l1)
    a1 = ops_arrow.to_arrow(l1)
    a2 = ops_arrow.to_arrow(l2)

    result = a1.concat(a2)
    expected = ops_arrow.to_arrow(l1 + l2)

    # assert result.object_type == expected.object_type
    assert fix_for_compare(result.to_pylist_tagged()) == fix_for_compare(
        expected.to_pylist_tagged()
    )


# @pytest.mark.flaky(reruns=3)
@given(
    list_lambda1=list_lambda_strategy(include_float=False),
    list_lambda2=list_lambda_strategy(include_float=False),
    leftOuter=st.booleans(),
    rightOuter=st.booleans(),
)
@settings(max_examples=EXAMPLES_PER_TEST, deadline=None)
def test_join2(list_lambda1, list_lambda2, leftOuter, rightOuter, weave_no_cache):
    l1, join1Fn = list_lambda1
    l2, join2Fn = list_lambda2
    # Call your join2_impl function
    alias1 = "alias1"
    alias2 = "alias2"
    l_result = weave.use(
        ops_primitives.join_2(
            l1, l2, join1Fn, join2Fn, alias1, alias2, leftOuter, rightOuter
        )
    )
    print("L1", l1)
    print("L2", l2)
    print("LEFT OUTER", leftOuter)
    print("RIGHT OUTER", rightOuter)
    a1 = ops_arrow.to_arrow(l1)
    a2 = ops_arrow.to_arrow(l2)
    arr_result = a1.join2(
        a2,
        join1Fn,
        join2Fn,
        alias1,
        alias2,
        leftOuter,
        rightOuter,
    )
    l_result_safe = ops_arrow.to_arrow(l_result).to_pylist_tagged()
    sorted_l_result_safe = sorted(l_result_safe, key=lambda x: json.dumps(x))
    sorted_arr_result = sorted(
        arr_result.to_pylist_tagged(), key=lambda x: json.dumps(x)
    )
    # print("L_RESULT_ORIG", l_result)
    # print("L_RESULT", sorted_l_result_safe)
    # print("ARR_RESULT", sorted_arr_result)
    with tag_store.new_tagging_context():
        compare_py(sorted_arr_result, sorted_l_result_safe)

    # # Add your assertions here
    # # For example, you can test the length of the result array


if __name__ == "__main__":
    test_to_compare_safe()
