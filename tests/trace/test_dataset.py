import pytest
import asyncio

import weave
from tests.trace.test_evaluate import Dataset
from weave.trace.context.tests_context import raise_on_captured_errors


def test_basic_dataset_lifecycle(client):
    for i in range(2):
        dataset = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
        ref = weave.publish(dataset)
        dataset2 = weave.ref(ref.uri()).get()
        assert (
            list(dataset2.rows)
            == list(dataset.rows)
            == [{"a": 5, "b": 6}, {"a": 7, "b": 10}]
        )


def test_dataset_iteration(client):
    dataset = weave.Dataset(rows=[{"a": 5, "b": 6}, {"a": 7, "b": 10}])
    rows = list(dataset)
    assert rows == [{"a": 5, "b": 6}, {"a": 7, "b": 10}]

    # Test that we can iterate multiple times
    rows2 = list(dataset)
    assert rows2 == rows


def test_pythonic_access(client):
    rows = [{"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}, {"a": 5}]
    ds = weave.Dataset(rows=rows)
    assert len(ds) == 5
    assert ds[0] == {"a": 1}

    with pytest.raises(IndexError):
        ds[-1]


def _top_level_logs(log):
    """Strip out internal logs from the log list"""
    return [l for l in log if not l.startswith("_")]


def test_dataset_laziness(client):
    """
    The intention of this test is to show that local construction of
    a dataset does not trigger any remote operations.
    """
    dataset = Dataset(rows=[{"input": i} for i in range(300)])
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == ["ensure_project_exists"]
    client.server.attribute_access_log = []

    length = len(dataset)
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == []

    length2 = len(dataset)
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == []

    assert length == length2

    for row in dataset:
        log = client.server.attribute_access_log
        assert _top_level_logs(log) == []


def test_published_dataset_laziness(client):
    """
    The intention of this test is to show that publishing a dataset,
    then iterating through the "gotten" version of the dataset has
    minimal remote operations - and importantly delays the fetching
    of the rows until they are actually needed.
    """
    dataset = Dataset(rows=[{"input": i} for i in range(300)])
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == ["ensure_project_exists"]
    client.server.attribute_access_log = []

    ref = weave.publish(dataset)
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == ["table_create", "obj_create"]
    client.server.attribute_access_log = []

    dataset = ref.get()
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == ["obj_read"]
    client.server.attribute_access_log = []

    length = len(dataset)
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == ["table_query_stats"]
    client.server.attribute_access_log = []

    length2 = len(dataset)
    log = client.server.attribute_access_log
    assert _top_level_logs(log) == []

    assert length == length2

    for i, row in enumerate(dataset):
        log = client.server.attribute_access_log
        # This is the critical part of the test - ensuring that
        # the rows are only fetched when they are actually needed.
        #
        # In a future improvement, we might eagerly fetch the next
        # page of results, which would result in this assertion changing
        # in that there would always be one more "table_query" than
        # the number of pages.
        assert _top_level_logs(log) == ["table_query"] * ((i // 100) + 1)


def test_dataset_from_calls(client):
    @weave.op
    def greet(name: str, age: int) -> str:
        return f"Hello {name}, you are {age}!"

    greet("Alice", 30)
    greet("Bob", 25)

    calls = client.get_calls()
    dataset = weave.Dataset.from_calls(calls)
    rows = list(dataset.rows)

    assert len(rows) == 2
    assert rows[0]["inputs"]["name"] == "Alice"
    assert rows[0]["inputs"]["age"] == 30
    assert rows[0]["output"] == "Hello Alice, you are 30!"
    assert rows[1]["inputs"]["name"] == "Bob"
    assert rows[1]["inputs"]["age"] == 25
    assert rows[1]["output"] == "Hello Bob, you are 25!"


def test_dataset_caching(client):
    ds = weave.Dataset(rows=[{"a": i} for i in range(200)])
    ref = weave.publish(ds)

    ds2 = ref.get()

    with raise_on_captured_errors():
        assert len(ds2) == 200


def test_dataset_select(client):
    original_rows = [{"id": i, "val": i * 2} for i in range(10)]
    ds = weave.Dataset(rows=original_rows)

    # Select first 3 using range
    selected_ds_range = ds.select(range(3))
    assert len(selected_ds_range) == 3
    assert list(selected_ds_range) == [
        {"id": 0, "val": 0},
        {"id": 1, "val": 2},
        {"id": 2, "val": 4},
    ]

    # Select specific indices using a list
    indices = [5, 2, 8]
    selected_ds_list = ds.select(indices)
    assert len(selected_ds_list) == 3
    assert list(selected_ds_list) == [
        {"id": 5, "val": 10},
        {"id": 2, "val": 4},
        {"id": 8, "val": 16},
    ]

    # Select with an empty list - should raise ValueError
    with pytest.raises(
        ValueError, match="Cannot select rows with an empty set of indices."
    ):
        ds.select([])

    # Select with indices that are out of order
    indices_unordered = [7, 1, 4, 1]
    selected_ds_unordered = ds.select(indices_unordered)
    assert len(selected_ds_unordered) == 4
    assert list(selected_ds_unordered) == [
        {"id": 7, "val": 14},
        {"id": 1, "val": 2},
        {"id": 4, "val": 8},
        {"id": 1, "val": 2},  # Duplicate index is allowed
    ]

    # Ensure original dataset is unchanged
    assert len(ds) == 10
    assert list(ds) == original_rows

    # Test index out of bounds
    with pytest.raises(IndexError):
        ds.select([0, 10])  # 10 is out of bounds

    # Test negative index (should fail in __getitem__)
    with pytest.raises(IndexError):
        ds.select([-1])


def test_add_rows(client):
    ds = weave.Dataset(name="test", rows=[{"a": i} for i in range(10)])
    ref = weave.publish(ds)

    ds = ref.get()
    ds2 = ds.add_rows([{"a": 10}])

    assert len(ds2) == 11
    assert ds2.rows[10]["a"] == 10

    ds3 = ds2.add_rows([{"a": 11}, {"a": 12}, {"a": 13}])
    assert len(ds3) == 14
    assert ds3.rows[12]["a"] == 12
    assert ds3.rows[11]["a"] == 11
    assert ds3.rows[10]["a"] == 10

    # Verify that publishing an already published dataset doesn't
    # do anything.
    ds4 = weave.publish(ds3).get()
    assert ds3.rows == ds4.rows


def test_add_rows_to_unsaved_dataset(client):
    ds = weave.Dataset(rows=[{"a": i} for i in range(10)])
    with pytest.raises(TypeError):
        ds.add_rows([{"a": 10}])


# Dataset.map tests

def test_dataset_map_basic(client):
    original_rows = [{"id": i, "val": i * 2} for i in range(5)]
    ds = weave.Dataset(rows=original_rows)

    # Use named parameters instead of row dictionary
    def add_doubled_val(val):
        return {"val_doubled": val * 2}

    mapped_ds = ds.map(add_doubled_val)

    assert len(mapped_ds) == 5
    expected_rows = [
        {"id": 0, "val": 0, "val_doubled": 0},
        {"id": 1, "val": 2, "val_doubled": 4},
        {"id": 2, "val": 4, "val_doubled": 8},
        {"id": 3, "val": 6, "val_doubled": 12},
        {"id": 4, "val": 8, "val_doubled": 16},
    ]
    assert list(mapped_ds) == expected_rows
    assert set(mapped_ds.columns_names) == {"id", "val", "val_doubled"}


async def add_tripled_val_async(val):
    await asyncio.sleep(0.01)  # Simulate async work
    return {"val_tripled": val * 3}


def test_dataset_map_async(client):
    original_rows = [{"id": i, "val": i * 2} for i in range(3)]
    ds = weave.Dataset(rows=original_rows)

    mapped_ds = ds.map(add_tripled_val_async)

    assert len(mapped_ds) == 3
    expected_rows = [
        {"id": 0, "val": 0, "val_tripled": 0},
        {"id": 1, "val": 2, "val_tripled": 6},
        {"id": 2, "val": 4, "val_tripled": 12},
    ]
    assert list(mapped_ds) == expected_rows
    assert set(mapped_ds.columns_names) == {"id", "val", "val_tripled"}


def test_dataset_map_failing_row(client):
    original_rows = [{"id": i, "val": i} for i in range(5)]
    ds = weave.Dataset(rows=original_rows)

    def fail_on_three(id):
        if id == 3:
            raise ValueError("ID cannot be 3!")
        return {"processed": True}

    with pytest.raises(ValueError, match="ID cannot be 3!"):
        ds.map(fail_on_three)


def test_dataset_map_uneven_dicts(client):
    original_rows = [{"id": i} for i in range(4)]
    ds = weave.Dataset(rows=original_rows)

    def add_conditional_cols(id):
        if id % 2 == 0:
            return {"is_even": True, "even_val": id * 10}
        else:
            return {"is_odd": True}

    # Note: weave.Table currently doesn't enforce strict schemas or fill missing vals with None
    # The behavior here reflects how weave.Table handles lists of dicts with varying keys.
    mapped_ds = ds.map(add_conditional_cols)

    assert len(mapped_ds) == 4
    expected_rows = [
        {"id": 0, "is_even": True, "even_val": 0}, # missing is_odd
        {"id": 1, "is_odd": True},               # missing is_even, even_val
        {"id": 2, "is_even": True, "even_val": 20},# missing is_odd
        {"id": 3, "is_odd": True},               # missing is_even, even_val
    ]
    assert list(mapped_ds) == expected_rows
    # The columns_names property gets the keys from the *first* row.
    assert set(mapped_ds.columns_names) == {"id", "is_even", "even_val"}


def test_dataset_map_immutability(client):
    original_rows = [{"id": i, "val": i} for i in range(3)]
    original_rows_copy = [r.copy() for r in original_rows] # Deep copy for comparison
    ds = weave.Dataset(rows=original_rows)

    # Use named parameters instead of row dictionary
    def add_square(val):
        return {"val_squared": val ** 2}

    mapped_ds = ds.map(add_square)

    # Assert mapped_ds is different
    assert len(mapped_ds) == 3
    assert list(mapped_ds)[0] == {"id": 0, "val": 0, "val_squared": 0}

    # Assert original dataset (ds) and its rows are unchanged
    assert len(ds) == 3
    assert list(ds) == original_rows_copy
    # Ensure the dictionaries within the original dataset were not mutated
    assert ds.rows[0] is original_rows[0] # Check object identity if rows were passed directly
    assert ds.rows[0] == original_rows_copy[0]


def test_dataset_map_with_specific_params(client):
    """Test mapping a function that takes specific parameters instead of a row dictionary."""
    original_rows = [{"id": i, "val": i * 2, "name": f"Item {i}"} for i in range(5)]
    ds = weave.Dataset(rows=original_rows)

    # Function that takes specific columns as parameters
    def multiply_val(val, id):
        return {"product": val * id}

    mapped_ds = ds.map(multiply_val)

    assert len(mapped_ds) == 5
    expected_rows = [
        {"id": 0, "val": 0, "name": "Item 0", "product": 0},
        {"id": 1, "val": 2, "name": "Item 1", "product": 2},
        {"id": 2, "val": 4, "name": "Item 2", "product": 8},
        {"id": 3, "val": 6, "name": "Item 3", "product": 18},
        {"id": 4, "val": 8, "name": "Item 4", "product": 32},
    ]
    assert list(mapped_ds) == expected_rows


def test_dataset_map_with_scalar_return(client):
    """Test mapping a function that returns a scalar value instead of a dictionary."""
    original_rows = [{"id": i, "val": i * 2} for i in range(5)]
    ds = weave.Dataset(rows=original_rows)

    # Function that takes specific columns and returns a scalar
    def sum_values(id, val):
        return id + val

    # The function's name "sum_values" should be used as the key
    mapped_ds = ds.map(sum_values)

    assert len(mapped_ds) == 5
    expected_rows = [
        {"id": 0, "val": 0, "sum_values": 0},
        {"id": 1, "val": 2, "sum_values": 3},
        {"id": 2, "val": 4, "sum_values": 6},
        {"id": 3, "val": 6, "sum_values": 9},
        {"id": 4, "val": 8, "sum_values": 12},
    ]
    assert list(mapped_ds) == expected_rows


def test_dataset_map_with_default_param(client):
    """Test mapping a function with default parameter values."""
    original_rows = [{"id": i, "val": i * 2} for i in range(5)]
    ds = weave.Dataset(rows=original_rows)

    # Function with a default parameter
    def process_with_default(val, multiplier=10):
        return {"scaled": val * multiplier}

    mapped_ds = ds.map(process_with_default)

    assert len(mapped_ds) == 5
    expected_rows = [
        {"id": 0, "val": 0, "scaled": 0},
        {"id": 1, "val": 2, "scaled": 20},
        {"id": 2, "val": 4, "scaled": 40},
        {"id": 3, "val": 6, "scaled": 60},
        {"id": 4, "val": 8, "scaled": 80},
    ]
    assert list(mapped_ds) == expected_rows


def test_dataset_map_missing_param(client):
    """Test mapping a function that expects a parameter not in the dataset."""
    original_rows = [{"id": i, "val": i * 2} for i in range(5)]
    ds = weave.Dataset(rows=original_rows)

    # Function expecting a parameter not in the dataset
    def needs_missing_param(val, missing_param):
        return {"result": val + missing_param}

    # Should raise an error because missing_param is not in the dataset
    with pytest.raises(ValueError, match="Function expects parameter 'missing_param'"):
        ds.map(needs_missing_param)


def test_dataset_map_with_lambda(client):
    """Test mapping with lambda functions."""
    ds = weave.Dataset(rows=[{"a": i, "b": i * 2} for i in range(5)])
    
    # Lambda that takes specific params
    mapped_ds = ds.map(lambda a, b: {"sum": a + b})
    assert len(mapped_ds) == 5
    assert mapped_ds[0] == {"a": 0, "b": 0, "sum": 0}
    assert mapped_ds[2] == {"a": 2, "b": 4, "sum": 6}
    
    # Lambda with a scalar return value (should get a generic key)
    mapped_ds = ds.map(lambda a, b: a * b)
    assert len(mapped_ds) == 5
    assert "<lambda>" in mapped_ds[0]  # Should use "<lambda>" as key
    assert mapped_ds[2]["<lambda>"] == 8  # 2 * 4


def test_dataset_map_parameter_reuse(client):
    """Test mapping when a function uses the same parameter in multiple ways."""
    ds = weave.Dataset(rows=[{"id": i, "val": i * 2} for i in range(3)])
    
    # Function that uses a parameter in multiple ways
    def reuse_param(id, val):
        return {
            "identity": id,
            "id_plus_val": id + val,
            "id_times_val": id * val,
        }
    
    mapped_ds = ds.map(reuse_param)
    
    assert len(mapped_ds) == 3
    assert mapped_ds[2] == {
        "id": 2, 
        "val": 4, 
        "identity": 2, 
        "id_plus_val": 6,  # 2 + 4
        "id_times_val": 8,  # 2 * 4
    }


def test_dataset_map_error_handling(client):
    """Test error handling in more complex scenarios."""
    ds = weave.Dataset(rows=[{"id": i, "val": i} for i in range(5)])
    
    # Function that raises different errors based on input
    def problematic_func(id, val):
        if id == 0:
            return {"ok": True}
        elif id == 1:
            return None  # Should be wrapped in a dict
        elif id == 2:
            # Type error when converting val to a list
            return {"error": list(val)}
        elif id == 3:
            # KeyError
            d = {}
            return {"error": d["nonexistent"]}
        else:
            # Should not get here in this test
            return {"ok": False}
    
    # Test None return value is handled
    mapped_ds = ds.map(lambda id, val: None if id == 3 else {"ok": id})
    assert "problematic_func" not in mapped_ds[1]
    assert mapped_ds[3]["<lambda>"] is None
    
    # Test list return is wrapped
    list_ds = ds.map(lambda id, val: [id, val] if id == 2 else {"ok": id})
    assert isinstance(list_ds[2]["<lambda>"], list)
    assert list_ds[2]["<lambda>"] == [2, 2]


def test_dataset_map_empty_dataset(client):
    """Test mapping on an empty dataset (should fail)."""
    # Create an empty dataset
    with pytest.raises(ValueError, match="empty list"):
        # This should fail during dataset creation, not during map
        ds = weave.Dataset(rows=[])
        ds.map(lambda x: x + 1)


def test_dataset_map_return_types(client):
    """Test mapping with different return types."""
    ds = weave.Dataset(rows=[{"id": i} for i in range(3)])
    
    # Test returning various data types
    def return_types(id):
        return {
            "str_val": str(id),
            "bool_val": bool(id),
            "list_val": [0, id],
            "dict_val": {"x": id},
            "none_val": None,
            "float_val": float(id),
        }
    
    types_ds = ds.map(return_types)
    
    # Check all types are preserved
    assert types_ds[1]["str_val"] == "1"
    assert types_ds[1]["bool_val"] is True
    assert types_ds[1]["list_val"] == [0, 1]
    assert types_ds[1]["dict_val"] == {"x": 1}
    assert types_ds[1]["none_val"] is None
    assert types_ds[1]["float_val"] == 1.0
    
    # Test returning a complex object directly
    class CustomClass:
        def __init__(self, value):
            self.value = value
    
    custom_ds = ds.map(lambda id: CustomClass(id + 100))
    
    # The CustomClass object should be stored under the function name
    assert custom_ds[1]["<lambda>"].value == 101


def test_dataset_map_typed_params(client):
    """Test mapping with type hints in function parameters."""
    ds = weave.Dataset(rows=[{"id": i, "num": str(i), "flag": i % 2 == 0} for i in range(5)])
    
    # Function with type annotations
    def typed_func(id: int, num: str, flag: bool) -> dict:
        # Convert num to int and add to id if flag is True
        result = int(num) + id if flag else id
        return {"result": result}
    
    mapped_ds = ds.map(typed_func)
    
    assert len(mapped_ds) == 5
    assert mapped_ds[0]["result"] == 0  # 0 + 0, flag=True
    assert mapped_ds[1]["result"] == 1  # Just id, flag=False
    assert mapped_ds[2]["result"] == 4  # 2 + 2, flag=True
    assert mapped_ds[3]["result"] == 3  # Just id, flag=False
    assert mapped_ds[4]["result"] == 8  # 4 + 4, flag=True


def test_dataset_map_empty_function(client):
    """Test mapping with an empty function (no parameters)."""
    ds = weave.Dataset(rows=[{"id": i, "val": i} for i in range(5)])
    
    # Function with no parameters
    def constant_func():
        return {"constant": 42}
    
    mapped_ds = ds.map(constant_func)
    
    # Should add the constant to every row
    assert len(mapped_ds) == 5
    for i in range(5):
        assert mapped_ds[i] == {"id": i, "val": i, "constant": 42}


def test_dataset_map_error_handling(client):
    """Test error handling in more complex scenarios."""
    ds = weave.Dataset(rows=[{"id": i, "val": i} for i in range(5)])
    
    # Function that raises different errors based on input
    def problematic_func(id, val):
        if id == 0:
            return {"ok": True}
        elif id == 1:
            return None  # Should be wrapped in a dict
        elif id == 2:
            # Type error when converting val to a list
            return {"error": list(val)}
        elif id == 3:
            # KeyError
            d = {}
            return {"error": d["nonexistent"]}
        else:
            # Should not get here in this test
            return {"ok": False}
    
    # Test None return value is handled
    mapped_ds = ds.map(lambda id, val: None if id == 3 else {"ok": id})
    assert "problematic_func" not in mapped_ds[1]
    assert mapped_ds[3]["<lambda>"] is None
    
    # Test list return is wrapped
    list_ds = ds.map(lambda id, val: [id, val] if id == 2 else {"ok": id})
    assert isinstance(list_ds[2]["<lambda>"], list)
    assert list_ds[2]["<lambda>"] == [2, 2]
