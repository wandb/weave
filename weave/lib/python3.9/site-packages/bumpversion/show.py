"""Functions for displaying information about the version."""

import dataclasses
from io import StringIO
from pathlib import Path
from pprint import pprint
from typing import Any, Optional

from bumpversion.bump import get_next_version
from bumpversion.config import Config
from bumpversion.context import get_context
from bumpversion.exceptions import BadInputError
from bumpversion.ui import print_error, print_info
from bumpversion.utils import recursive_sort_dict


def output_default(value: dict) -> None:
    """Output the value with key=value or just value if there is only one item."""
    if len(value) == 1:
        print_info(next(iter(value.values())))
    else:
        buffer = StringIO()
        pprint(value, stream=buffer, sort_dicts=True)
        print_info(buffer.getvalue())


def output_yaml(value: dict) -> None:
    """Output the value as yaml."""
    from bumpversion.yaml_dump import dump

    print_info(dump(recursive_sort_dict(value)))


def output_json(value: dict) -> None:
    """Output the value as json."""
    import json

    def default_encoder(obj: Any) -> str:
        if dataclasses.is_dataclass(obj):
            return str(obj)
        elif isinstance(obj, type):
            return obj.__name__
        elif isinstance(obj, Path):
            return str(obj)
        raise TypeError(f"Object of type {type(obj), str(obj)} is not JSON serializable")

    print_info(json.dumps(value, sort_keys=True, indent=2, default=default_encoder))


OUTPUTTERS = {
    "yaml": output_yaml,
    "json": output_json,
    "default": output_default,
}


def resolve_name(obj: Any, name: str, default: Any = None, err_on_missing: bool = False) -> Any:
    """
    Get a key or attr ``name`` from obj or default value.

    Copied and modified from Django Template variable resolutions

    Resolution methods:

    - Mapping key lookup
    - Attribute lookup
    - Sequence index

    Args:
        obj: The object to access
        name: A dotted name to the value, such as ``mykey.0.name``
        default: If the name cannot be resolved from the object, return this value
        err_on_missing: Raise a `BadInputError` if the name cannot be resolved

    Returns:
        The value at the resolved name or the default value.

    Raises:
        BadInputError: If we cannot resolve the name and `err_on_missing` is `True`
        AttributeError: If a @property decorator raised it
        TypeError: If a @property decorator raised it

    # noqa: DAR401
    """
    lookups = name.split(".")
    current = obj
    try:  # catch-all for unexpected failures
        for bit in lookups:
            try:  # dictionary lookup
                current = current[bit]
                # ValueError/IndexError are for numpy.array lookup on
                # numpy < 1.9 and 1.9+ respectively
            except (TypeError, AttributeError, KeyError, ValueError, IndexError):
                try:  # attribute lookup
                    current = getattr(current, bit)
                except (TypeError, AttributeError):
                    # Reraise if the exception was raised by a @property
                    if bit in dir(current):
                        raise
                    try:  # list-index lookup
                        current = current[int(bit)]
                    except (
                        IndexError,  # list index out of range
                        ValueError,  # invalid literal for int()
                        KeyError,  # current is a dict without `int(bit)` key
                        TypeError,
                    ):  # un-subscript-able object
                        return default
        return current
    except Exception as e:  # pragma: no cover
        if err_on_missing:
            raise BadInputError(f"Could not resolve '{name}'") from e
        else:
            return default


def do_show(*args, config: Config, format_: str = "default", increment: Optional[str] = None) -> None:
    """Show current version or configuration information."""
    config_dict = config.model_dump()
    ctx = get_context(config)

    if increment:
        version = config.version_config.parse(config.current_version)
        next_version = get_next_version(version, config, increment, None)
        next_version_str = config.version_config.serialize(next_version, ctx)
        config_dict["new_version"] = next_version_str

    try:
        if "all" in args or not args:
            show_items = config_dict
        else:
            show_items = {key: resolve_name(config_dict, key) for key in args}

        OUTPUTTERS.get(format_, OUTPUTTERS["default"])(show_items)
    except BadInputError as e:
        print_error(e.message)
