import pytest

from weave.trace.grid import Grid, Row


def test_grid_creation():
    grid = Grid()
    assert grid.num_rows == 0
    assert grid.num_columns == 0
    assert grid.columns == []
    assert grid.rows == []


def test_add_column():
    grid = Grid()
    grid.add_column("name")
    grid.add_column("age", label="User Age")

    assert grid.num_columns == 2
    assert grid.columns[0].id == "name"
    assert grid.columns[0].label is None
    assert grid.columns[0].display_name == "name"
    assert grid.columns[1].id == "age"
    assert grid.columns[1].label == "User Age"
    assert grid.columns[1].display_name == "User Age"


def test_add_row():
    grid = Grid()
    grid.add_column("name")
    grid.add_column("age")

    grid.add_row(["Alice", 30])
    grid.add_row(["Bob", 25])

    assert grid.num_rows == 2
    assert grid.rows[0] == ["Alice", 30]
    assert grid.rows[1] == ["Bob", 25]


def test_add_row_validation():
    grid = Grid()
    grid.add_column("name")

    with pytest.raises(ValueError):
        grid.add_row(["Alice", 30])  # Too many values


def test_get_row():
    grid = Grid()
    grid.add_column("name")
    grid.add_column("age")
    grid.add_row(["Alice", 30])

    row = grid.get_row(0)
    assert isinstance(row, Row)
    assert row["name"] == "Alice"
    assert row["age"] == 30
    assert row[0] == "Alice"
    assert row[1] == 30
    assert row.name == "Alice"
    assert row.age == 30


def test_get_row_errors():
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
        row.invalid  # Invalid attribute name


def test_get_column_values():
    grid = Grid()
    grid.add_column("name")
    grid.add_column("age")
    grid.add_row(["Alice", 30])
    grid.add_row(["Bob", 25])
    grid.add_row(["Charlie", 35])

    assert grid.get_column_values("name") == ["Alice", "Bob", "Charlie"]
    assert grid.get_column_values("age") == [30, 25, 35]
    assert grid.get_column_values(0) == ["Alice", "Bob", "Charlie"]
    assert grid.get_column_values(1) == [30, 25, 35]


def test_get_column_values_errors():
    grid = Grid()
    grid.add_column("name")
    grid.add_row(["Alice"])

    with pytest.raises(KeyError):
        grid.get_column_values("invalid")  # Invalid column name

    with pytest.raises(IndexError):
        grid.get_column_values(1)  # Invalid column index

    with pytest.raises(TypeError):
        grid.get_column_values(1.5)  # Invalid key type
