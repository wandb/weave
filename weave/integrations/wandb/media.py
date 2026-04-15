"""Conversion helpers from wandb media types to Weave-native types.

wandb.Image  → PIL.Image.Image (via the .image property, works for all
               construction modes: numpy array, PIL image, file path)
               Falls back to weave.Content.from_path() when PIL is unavailable.

Other wandb Media subclasses → TypeError (not supported).
Non-media values              → returned unchanged.
"""

from __future__ import annotations

import warnings
from typing import Any

# wandb — required for this module; callers must guard on _WANDB_AVAILABLE
try:
    import wandb

    # Private base-class import used to detect unsupported wandb media types
    # without enumerating every known type explicitly.
    from wandb.sdk.data_types.base_types.media import Media as _WandbMedia

    _WANDB_AVAILABLE = True
except ImportError:
    _WANDB_AVAILABLE = False

# PIL — optional; preferred target for wandb.Image conversion
try:
    from PIL import Image as _PILImage  # noqa: F401  (imported for isinstance checks)

    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

from weave.type_wrappers.Content.content import Content as _Content


def _unwrap_value(val: Any, column: str, warned: set[type]) -> Any:
    """Convert a wandb media cell value to the appropriate Weave-native type.

    Args:
        val: The cell value to convert.
        column: Column name, used in error/warning messages.
        warned: Set of wandb types already warned about (mutated in-place).

    Returns:
        A Weave-native object (PIL Image or weave.Content), or the original
        value if no conversion is needed.

    Raises:
        ValueError: If a supported media type has no accessible data or path.
        TypeError: If the value is an unsupported wandb Media subclass.
    """
    if not _WANDB_AVAILABLE:
        return val

    # --- wandb.Image ---
    if isinstance(val, wandb.Image):
        if wandb.Image not in warned:
            warnings.warn(
                "wandb.Image values are converted to PIL.Image for Weave. "
                "Caption and other metadata are discarded.",
                stacklevel=4,
            )
            warned.add(wandb.Image)

        # .image works for all construction modes (numpy array, PIL Image, file path)
        if _PIL_AVAILABLE:
            pil = val.image
            if pil is not None:
                return pil

        # Fallback: store raw bytes via Content (e.g. PIL not installed, or BMP)
        if val._path is not None:
            return _Content.from_path(val._path)

        raise ValueError(
            f"Cannot convert wandb.Image in column {column!r}: "
            "no PIL image or file path is available."
        )

    # --- unsupported wandb Media subclass ---
    if isinstance(val, _WandbMedia):
        raise TypeError(
            f"Unsupported wandb media type {type(val).__name__!r} "
            f"in column {column!r}. "
            "Only wandb.Image is supported."
        )

    return val
