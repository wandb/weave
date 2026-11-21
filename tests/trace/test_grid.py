import locale
import subprocess
import sys

import pytest

from weave.trace.display.grid import Grid, Row, display_value


@pytest.mark.parametrize("environment_locale", ["C", "weave_invalid_locale"])
def test_import_preserves_locale(environment_locale):
    code = """
import importlib
import locale
import os
import sys
from unittest.mock import Mock

locale.setlocale(locale.LC_ALL, "C")
original_setlocale = locale.setlocale
before = original_setlocale(locale.LC_ALL)
os.environ["LC_ALL"] = sys.argv[1]
setter = Mock(wraps=original_setlocale)
locale.setlocale = setter

importlib.import_module("weave")

assert original_setlocale(locale.LC_ALL) == before
mutations = [
    call for call in setter.call_args_list
    if (len(call.args) > 1 and call.args[1] is not None)
    or call.kwargs.get("locale") is not None
]
assert mutations == [], mutations
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, environment_locale],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    ("separator", "grouping", "value", "expected"),
    [
        (",", [3, 0], 1234567, "1,234,567"),
        (".", [3, 0], -1234567, "-1.234.567"),
        (",", [3, 2, 0], 1234567, "12,34,567"),
        ("", [], 1234567, "1234567"),
    ],
)
def test_display_integer_uses_current_locale(
    monkeypatch, separator, grouping, value, expected
):
    conventions = locale.localeconv()
    conventions.update(thousands_sep=separator, grouping=grouping)
    monkeypatch.setattr(locale, "localeconv", lambda: conventions)

    assert display_value(value) == expected


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

    with pytest.raises(ValueError, match="does not match number of columns"):
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
        _ = row.invalid  # Invalid attribute name


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
