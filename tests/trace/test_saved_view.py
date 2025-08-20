import datetime

import pytest

import weave
from weave.flow.saved_view import (
    Filter,
    Filters,
    filters_to_query,
    query_to_filters,
    to_seconds,
)
from weave.trace.api import ObjectRef
from weave.trace_server import trace_server_interface as tsi


def test_to_seconds():
    assert to_seconds(None) is None
    assert to_seconds("") is None
    assert to_seconds(1) == 1
    assert to_seconds(5.3) == 5.3
    assert to_seconds("5.3") == 5.3
    assert to_seconds("2025-03-02T00:00:00Z") == 1740873600.0
    dt = datetime.datetime(2025, 3, 2, 0, 0, 0, tzinfo=datetime.timezone.utc)
    assert to_seconds(dt) == 1740873600.0


def test_filters_to_query():
    assert filters_to_query(None) is None
    assert filters_to_query([]) is None


def test_query_to_filters_none():
    assert query_to_filters(None) is None


def test_query_to_filters_one_filter():
    query = tsi.Query(**{"$expr": {"$eq": [{"$getField": "rank"}, {"$literal": 1}]}})
    assert query_to_filters(query) == [
        Filter(field="rank", operator="(number): =", value=1)
    ]

    query = tsi.Query(
        **{
            "$expr": {
                "$gt": [
                    {"$getField": "completion_token_cost"},
                    {"$literal": 25},
                ],
            }
        }
    )
    assert query_to_filters(query) == [
        Filter(field="completion_token_cost", operator="(number): >", value=25)
    ]

    query = tsi.Query(
        **{
            "$expr": {
                "$eq": [{"$getField": "inputs.model"}, {"$literal": "gpt-4o-mini"}]
            }
        }
    )
    assert query_to_filters(query) == [
        Filter(field="inputs.model", operator="(string): equals", value="gpt-4o-mini")
    ]


def test_query_to_filters_multiple_filters():
    query = tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": "inputs.model"},
                            {"$literal": "gpt-4o-mini"},
                        ]
                    },
                    {
                        "$eq": [
                            {"$getField": "output.object"},
                            {"$literal": "chat.completion"},
                        ]
                    },
                ]
            }
        }
    )
    assert query_to_filters(query) == [
        Filter(field="inputs.model", operator="(string): equals", value="gpt-4o-mini"),
        Filter(
            field="output.object", operator="(string): equals", value="chat.completion"
        ),
    ]


def test_roundtrip_operators():
    cases: Filters = [
        Filter(field="test", operator="(string): contains", value="foo"),
        Filter(field="test", operator="(string): equals", value="foo"),
        Filter(field="test", operator="(string): in", value=["A", "B", "C"]),
        Filter(field="test", operator="(number): =", value=42),
        Filter(field="test", operator="(number): !=", value=42),
        Filter(field="test", operator="(number): <", value=42),
        Filter(field="test", operator="(number): <=", value=5.0),
        Filter(field="test", operator="(number): >", value=42),
        Filter(field="test", operator="(number): >=", value=5.0),
        # We can't round trip bool is operator, because it gets converted to a string equals
        Filter(field="test", operator="(any): isEmpty", value=None),
        Filter(field="test", operator="(any): isNotEmpty", value=None),
        # There is special handling for started_at because we convert it to a numeric filter
        Filter(
            field="started_at", operator="(date): after", value="2025-01-01T00:00:00"
        ),
        Filter(
            field="started_at", operator="(date): before", value="2025-01-01T00:00:00"
        ),
    ]
    for case in cases:
        filters = [case]
        query = filters_to_query(filters)
        filters2 = query_to_filters(query)
        assert filters == filters2


def test_filter_op_without_client():
    """If we haven't done an init, we don't know what entity/project a non-qualified op name is in."""
    with pytest.raises(
        ValueError, match="Must specify Op URI if entity/project is not known"
    ):
        weave.SavedView("traces", "My saved view").filter_op(
            "Evaluation.predict_and_score"
        )


def test_filter_op_with_client(client):
    view = weave.SavedView("traces", "My saved view").filter_op(
        "Evaluation.predict_and_score"
    )
    assert view.base.definition.filter.op_names == [
        "weave:///shawn/test-project/op/Evaluation.predict_and_score:*"
    ]
    view.filter_op(None)
    assert view.base.definition.filter is None


def test_filter_manipulation():
    view = weave.SavedView("traces", "My saved view")

    view.add_filter("inputs.model", "equals", "gpt-3.5-turbo")
    assert view.base.definition.query == tsi.Query(
        **{
            "$expr": {
                "$and": [
                    {
                        "$eq": [
                            {"$getField": "inputs.model"},
                            {"$literal": "gpt-3.5-turbo"},
                        ]
                    },
                ]
            }
        }
    )
    view.remove_filters()
    assert view.base.definition.query is None

    view.add_filter("inputs.model", "equals", "gpt-3.5-turbo")
    view.remove_filter("inputs.model")
    assert view.base.definition.query is None

    view.add_filter("inputs.model", "equals", "gpt-3.5-turbo")
    view.remove_filter("inputs.model")
    assert view.base.definition.query is None


def test_column_manipulation():
    view = weave.SavedView("traces", "My saved view")

    # Removing a column that doesn't exist doesn't error
    view.remove_column("inputs.foo")

    # Removing all columns is same as having none specified
    view.add_column("inputs.foo")
    view.remove_column("inputs.foo")
    assert view.base.definition.columns is None

    view.set_columns("id", "inputs.model")
    assert len(view.base.definition.columns) == 2
    assert view.base.definition.columns[0].path == ["id"]
    assert view.base.definition.columns[0].label is None
    assert view.base.definition.columns[1].path == ["inputs", "model"]
    assert view.base.definition.columns[1].label is None

    assert view.column_index(1) == 1
    assert view.column_index("inputs.model") == 1
    with pytest.raises(ValueError, match='Column "foo" not found'):
        view.column_index("foo")

    view.remove_column(0)
    assert len(view.base.definition.columns) == 1
    assert view.base.definition.columns[0].path == ["inputs", "model"]

    view.rename_column(0, "new_inputs_model_name")
    assert view.base.definition.columns[0].label == "new_inputs_model_name"

    view.remove_columns()
    assert view.base.definition.columns is None

    view.add_column("inputs.foo")
    view.insert_column(0, "inputs.bar")
    assert len(view.base.definition.columns) == 2
    assert view.base.definition.columns[0].path == ["inputs", "bar"]
    assert view.base.definition.columns[1].path == ["inputs", "foo"]
    view.remove_columns("inputs.bar")
    assert len(view.base.definition.columns) == 1
    assert view.base.definition.columns[0].path == ["inputs", "foo"]


def test_saved_view_create(client):
    view = weave.SavedView("traces", "My saved view").hide_column("feedback").save()
    assert view.label == "My saved view"
    assert isinstance(view.ref, ObjectRef)


def test_saved_view_load(client):
    saved_view = weave.SavedView("traces", "My saved view")
    saved_view.show_column("attributes.weave.client_version")
    saved_view.save()
    uri = saved_view.ref.uri()
    loaded_view = weave.SavedView.load(uri)
    assert loaded_view.label == saved_view.label
    assert loaded_view.view_type == saved_view.view_type
    assert loaded_view.base.definition.cols["attributes.weave.client_version"] is True


def test_saved_view_column_pinning():
    view = weave.SavedView("traces", "My saved view")

    # Pin two columns to the left and two to the right.
    # Confirm order including default pin is as expected.
    view.pin_column_left("output.col_a")
    view.pin_column_left("output.col_b")
    view.pin_column_right("output.col_c")
    view.pin_column_right("output.col_d")
    assert view.base.definition.pin.left == [
        "CustomCheckbox",
        "op_name",
        "output.col_a",
        "output.col_b",
    ]
    assert view.base.definition.pin.right == ["output.col_c", "output.col_d"]

    # Unpinning columns removes them from the pin list
    view.unpin_column("output.col_a")
    assert view.base.definition.pin.left == [
        "CustomCheckbox",
        "op_name",
        "output.col_b",
    ]
    view.unpin_column("output.col_c")
    assert view.base.definition.pin.right == ["output.col_d"]

    # Pin a column that is currently right to left and left to right
    view.pin_column_left("output.col_d")
    assert view.base.definition.pin.left == [
        "CustomCheckbox",
        "op_name",
        "output.col_b",
        "output.col_d",
    ]
    assert view.base.definition.pin.right == []
    view.pin_column_right("output.col_b")
    assert view.base.definition.pin.left == [
        "CustomCheckbox",
        "op_name",
        "output.col_d",
    ]
    assert view.base.definition.pin.right == ["output.col_b"]


@weave.op
def chat_completion_create(
    custom_id: str,
    model: str,
    temperature: float,
    max_tokens: int,
    messages: list[dict[str, str]],
    stream: bool,
) -> str:
    return "Hello, world!"


def make_calls(client):
    chat_completion_create(
        custom_id="1",
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=500,
        messages=[{"role": "user", "content": "Hello, world!"}],
        stream=False,
    )
    chat_completion_create(
        custom_id="2",
        model="gpt-3.5-turbo",
        temperature=0.6,
        max_tokens=400,
        messages=[{"role": "user", "content": "Hello, world!"}],
        stream=False,
    )
    chat_completion_create(
        custom_id="3",
        model="gpt-3.5-turbo",
        temperature=0.5,
        max_tokens=300,
        messages=[{"role": "user", "content": "Hello, world!"}],
        stream=False,
    )
    chat_completion_create(
        custom_id="4",
        model="gpt-3.5-turbo",
        temperature=0.4,
        max_tokens=200,
        messages=[{"role": "user", "content": "Hello, world!"}],
        stream=True,
    )
    chat_completion_create(
        custom_id="5",
        model="gpt-3.5-turbo",
        temperature=0.8,
        max_tokens=100,
        messages=[{"role": "user", "content": "Hello, world!"}],
        stream=True,
    )


def test_saved_view_column_select(client):
    make_calls(client)
    view = weave.SavedView("traces", "My saved view")
    view.add_column("inputs.custom_id")
    calls = view.get_calls()
    assert len(calls) == 5
    grid = view.to_grid()
    assert grid.num_columns == 1
    assert grid["inputs.custom_id"].to_list() == ["1", "2", "3", "4", "5"]


def test_saved_view_repr_pretty():
    view = weave.SavedView("traces", "My saved view")
    # Test that _repr_pretty_ doesn't raise an exception
    view.add_column("inputs.model")
    view.hide_column("output")
    view.pin_column_right("inputs.model")
    view.add_filter("inputs.model", "equals", "gpt-3.5-turbo")
    view.add_sort("inputs.temperature", "desc")
    view.page_size(10)

    # Create a mock printer object to test _repr_pretty_
    class MockPrinter:
        def __init__(self):
            self.text_content = ""

        def text(self, content):
            self.text_content += content

    p = MockPrinter()
    view._repr_pretty_(p, False)

    # Verify that the representation contains expected content
    assert "My saved view" in p.text_content
    assert "traces" in p.text_content
    assert "inputs.model" in p.text_content
    assert "gpt-3.5-turbo" in p.text_content

    # Test cycle case
    p = MockPrinter()
    view._repr_pretty_(p, True)
    assert p.text_content == "SavedView(...)"
