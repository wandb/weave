"""
This module provides import machinery for known optional modules used by weave.

We use this tooling to give:
    1. Users: a nice error messages when they try to use a module that's not installed.
    2. Devs: Nice auto-complete in their IDE

To include a module:
    1. Import the module under TYPE_CHECKING
    2. Add an overload to the get_module function
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    import dspy as _dspy
    import numpy as _np
    import pandas as _pd
    import wandb as _wandb


@overload
def get_module(name: Literal["numpy"]) -> _np: ...
@overload
def get_module(name: Literal["pandas"]) -> _pd: ...
@overload
def get_module(name: Literal["wandb"]) -> _wandb: ...
@overload
def get_module(name: Literal["dspy"]) -> _dspy: ...
def get_module(name: str, error_message: str | None = None) -> ModuleType | None:
    try:
        module = import_module(name)
    except (ImportError, ModuleNotFoundError):
        if error_message is None:
            error_message = f"Unable to import {name}"

        raise ImportError(error_message) from None
    return module
