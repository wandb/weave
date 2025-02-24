from unittest.mock import patch

import pytest

import weave
from weave.trace.refs import ObjectRef
from weave.trace_server.refs_internal import (
    DICT_KEY_EDGE_NAME,
    LIST_INDEX_EDGE_NAME,
)


def test_dict_refs(client):
    d = client.save({"a": 1, "b": 2}, name="d")

    assert d["a"] == 1
    assert isinstance(d["a"].ref, ObjectRef)
    assert d["a"].ref.is_descended_from(d.ref)
    assert d["a"].ref.extra == (DICT_KEY_EDGE_NAME, "a")

    assert d["b"] == 2
    assert isinstance(d["b"].ref, ObjectRef)
    assert d["b"].ref.is_descended_from(d.ref)
    assert d["b"].ref.extra == (DICT_KEY_EDGE_NAME, "b")


def test_dict_iter(client):
    d_orig = client.save({"a": 1, "b": 2, "c": 3}, name="d")
    d = dict(d_orig)
    with pytest.raises(AttributeError):
        d.ref

    assert d["a"] == 1
    assert isinstance(d["a"].ref, ObjectRef)
    assert d["a"].ref.is_descended_from(d_orig.ref)
    assert d["a"].ref.extra == (DICT_KEY_EDGE_NAME, "a")

    assert d["b"] == 2
    assert isinstance(d["b"].ref, ObjectRef)
    assert d["b"].ref.is_descended_from(d_orig.ref)
    assert d["b"].ref.extra == (DICT_KEY_EDGE_NAME, "b")


def test_list_refs(client):
    l = client.save([1, 2], name="l")

    assert l[0] == 1
    assert isinstance(l[0].ref, ObjectRef)
    assert l[0].ref.is_descended_from(l.ref)
    assert l[0].ref.extra == (LIST_INDEX_EDGE_NAME, "0")

    assert l[1] == 2
    assert isinstance(l[1].ref, ObjectRef)
    assert l[1].ref.is_descended_from(l.ref)
    assert l[1].ref.extra == (LIST_INDEX_EDGE_NAME, "1")


def test_list_iter(client):
    l_orig = client.save([1, 2], name="l")
    l = list(l_orig)
    with pytest.raises(AttributeError):
        l.ref

    assert l[0] == 1
    assert l[0].ref.is_descended_from(l_orig.ref)
    assert isinstance(l[0].ref, ObjectRef)

    assert l[1] == 2
    assert l[1].ref.is_descended_from(l_orig.ref)
    assert isinstance(l[1].ref, ObjectRef)


def test_row_ref_inside_dict(client):
    """Test the case where a Weave object has a value that is a ref to a row within a Dataset.

    This is approximately the case of accessing the row used as the input
    to a predict_and_score function in an Evaluation.
    """
    # Create a dataset with 3 rows, get a ref to the second row
    rows = [{"a": 1, "b": 2}, {"a": 3, "b": 4}, {"a": 5, "b": 6}]
    dataset = weave.Dataset(rows=rows)
    saved = client.save(dataset, "my-dataset")
    assert isinstance(saved.rows, weave.trace.vals.WeaveTable)
    second_row = saved.rows[1]
    assert isinstance(second_row.ref, ObjectRef)

    # Create a dict pointing to the second row
    inputs = {"example": second_row.ref.uri()}
    saved_dict = client.save(inputs, "my-dict")

    # We want to spy on the table_query method to ensure it is only returning
    # the row that was requested.
    original_function = weave.trace_server_bindings.caching_middleware_trace_server.CachingMiddlewareTraceServer.table_query
    with patch(
        "weave.trace_server_bindings.caching_middleware_trace_server.CachingMiddlewareTraceServer.table_query",
        autospec=True,
    ) as mock_table_query:
        # Store the original return value in a variable by capturing it in the side effect
        original_return = None

        def side_effect(*args, **kwargs):
            nonlocal original_return
            original_return = original_function(*args, **kwargs)
            return original_return

        mock_table_query.side_effect = side_effect

        example = saved_dict["example"]
        assert example == second_row
        mock_table_query.assert_called_once()

        # Confirm that we only accessed a single row and not the entire dataset
        assert len(original_return.rows) == 1
