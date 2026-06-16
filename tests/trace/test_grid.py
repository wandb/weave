import pytest

from weave.trace.display.grid import Grid, Row


def test_grid_build_columns_and_rows():
    """Empty grid, column metadata (id/label/display_name), and row append + validation."""
    grid = Grid()
    assert grid.num_rows == 0
    assert grid.num_columns == 0
    assert grid.columns == []
    assert grid.rows == []

    grid.add_column("name")
    grid.add_column("age", label="User Age")
    assert grid.num_columns == 2
    assert grid.columns[0].id == "name"
    assert grid.columns[0].label is None
    assert grid.columns[0].display_name == "name"
    assert grid.columns[1].id == "age"
    assert grid.columns[1].label == "User Age"
    assert grid.columns[1].display_name == "User Age"

    grid.add_row(["Alice", 30])
    grid.add_row(["Bob", 25])
    assert grid.num_rows == 2
    assert grid.rows[0] == ["Alice", 30]
    assert grid.rows[1] == ["Bob", 25]

    with pytest.raises(ValueError, match="does not match number of columns"):
        grid.add_row(["Carol", 40, "extra"])


def test_grid_row_and_column_access():
    """Row access by name/index/attribute and get_column_values by name/index."""
    grid = Grid()
    grid.add_column("name")
    grid.add_column("age")
    grid.add_row(["Alice", 30])
    grid.add_row(["Bob", 25])
    grid.add_row(["Charlie", 35])

    row = grid.get_row(0)
    assert isinstance(row, Row)
    assert row["name"] == "Alice"
    assert row["age"] == 30
    assert row[0] == "Alice"
    assert row[1] == 30
    assert row.name == "Alice"
    assert row.age == 30

    assert grid.get_column_values("name") == ["Alice", "Bob", "Charlie"]
    assert grid.get_column_values("age") == [30, 25, 35]
    assert grid.get_column_values(0) == ["Alice", "Bob", "Charlie"]
    assert grid.get_column_values(1) == [30, 25, 35]


def test_grid_access_errors():
    """Out-of-range row, bad row keys, and bad get_column_values keys all raise."""
    grid = Grid()
    grid.add_column("name")
    grid.add_row(["Alice"])

    with pytest.raises(IndexError):
        grid.get_row(1)  # Out of range

    row = grid.get_row(0)
    with pytest.raises(KeyError):
        row["invalid"]  # Invalid column name
    with pytest.raises(IndexError):
        row[1]  # Invalid column index
    with pytest.raises(TypeError):
        row[1.5]  # Invalid key type
    with pytest.raises(AttributeError):
        _ = row.invalid  # Invalid attribute name

    with pytest.raises(KeyError):
        grid.get_column_values("invalid")  # Invalid column name
    with pytest.raises(IndexError):
        grid.get_column_values(1)  # Invalid column index
    with pytest.raises(TypeError):
        grid.get_column_values(1.5)  # Invalid key type
