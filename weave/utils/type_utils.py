"""Type-detection helpers for external library types.

These functions identify objects from optional dependencies (pandas, wandb, etc.)
using typename introspection so that the libraries themselves need not be imported.
"""

from __future__ import annotations

from typing import Any


def is_pandas_data_frame(obj: Any) -> bool:
    """Detect a pandas DataFrame without importing pandas."""
    typename = obj.__class__.__module__ + "." + obj.__class__.__name__
    return typename.startswith("pandas.") and "DataFrame" in typename


def is_wandb_table(obj: Any) -> bool:
    """Detect a wandb Table (or subclass) without importing wandb."""
    typename = obj.__class__.__module__ + "." + obj.__class__.__name__
    return typename.startswith("wandb.") and "Table" in typename
