"""A simple YAML dumper to avoid extra dependencies."""

import datetime
from collections import UserDict
from io import StringIO
from textwrap import indent
from typing import Any, Callable, Union

DumperFunc = Callable[[Any], str]


class YAMLDumpers(UserDict):
    """Registry of YAML dumpers."""

    def add_dumper(self, data_type: type, dumper: DumperFunc) -> None:
        """Add a YAML dumper."""
        self.data[data_type] = dumper


YAML_DUMPERS = YAMLDumpers()

INDENT = "  "


def dump(data: Any) -> str:
    """Dump a value to a string buffer."""
    data_types = type(data).__mro__
    for data_type in data_types:
        if data_type in YAML_DUMPERS:
            return YAML_DUMPERS[data_types[0]](data)

    return YAML_DUMPERS[str](str(data))


def format_str(val: str) -> str:
    """Return a YAML representation of a string."""
    val = val.replace("\\", "\\\\").replace("\n", "\\n")
    return f'"{val}"'


YAML_DUMPERS.add_dumper(str, format_str)


def format_int(val: int) -> str:
    """Return a YAML representation of an int."""
    return str(val)


YAML_DUMPERS.add_dumper(int, format_int)


def format_float(data: float) -> str:
    """Return a YAML representation of a float."""
    inf_value = 1e300

    if data != data:
        value = ".nan"
    elif data == inf_value:
        value = ".inf"
    elif data == -inf_value:
        value = "-.inf"
    else:
        value = repr(data).lower()
        # Note that in some cases `repr(data)` represents a float number
        # without the decimal parts.  For instance:
        #   >>> repr(1e17)
        #   '1e17'
        # Unfortunately, this is not a valid float representation according
        # to the definition of the `!!float` tag.  We fix this by adding
        # '.0' before the 'e' symbol.
        if "." not in value and "e" in value:
            value = value.replace("e", ".0e", 1)
    return str(value)


YAML_DUMPERS.add_dumper(float, format_float)


def format_bool(val: bool) -> str:
    """Return a YAML representation of a bool."""
    return "true" if val else "false"


YAML_DUMPERS.add_dumper(bool, format_bool)


def format_dict(val: dict) -> str:
    """Return a YAML representation of a dict."""
    buffer = StringIO()

    for key, value in sorted(val.items()):
        rendered_value = dump(value).strip()
        if isinstance(value, (dict, list, tuple)):
            rendered_value = f"\n{indent(rendered_value, INDENT)}"
        else:
            rendered_value = f" {rendered_value}"
        buffer.write(f"{key}:{rendered_value}\n")

    return buffer.getvalue()


YAML_DUMPERS.add_dumper(dict, format_dict)


def format_sequence(val: Union[list, tuple]) -> str:
    """Return a string representation of a value."""
    buffer = StringIO()

    for item in val:
        rendered_value = dump(item).strip()
        if isinstance(item, dict):
            rendered_value = indent(rendered_value, INDENT).strip()

        if isinstance(item, (list, tuple)):
            rendered_value = f"\n{indent(rendered_value, INDENT)}"
        else:
            rendered_value = f" {rendered_value}"
        buffer.write(f"-{rendered_value}\n")

    return buffer.getvalue()


YAML_DUMPERS.add_dumper(list, format_sequence)
YAML_DUMPERS.add_dumper(tuple, format_sequence)


def format_none(_: None) -> str:
    """Return a YAML representation of None."""
    return "null"


YAML_DUMPERS.add_dumper(type(None), format_none)


def format_date(val: datetime.date) -> str:
    """Return a YAML representation of a date."""
    return val.isoformat()


YAML_DUMPERS.add_dumper(datetime.date, format_date)


def format_datetime(val: datetime.datetime) -> str:
    """Return a string representation of a value."""
    return val.isoformat(" ")


YAML_DUMPERS.add_dumper(datetime.datetime, format_datetime)
