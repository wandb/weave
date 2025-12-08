from __future__ import annotations

from collections.abc import Callable
from typing import Any, get_args, get_origin

import marimo as mo


def _is_marimo_widget(obj: Any) -> bool:
    """Check if an object is a marimo UI widget.

    Args:
        obj: The object to check.

    Returns:
        True if the object appears to be a marimo widget, False otherwise.
    """
    if obj is None:
        return False

    # Check if it has the 'value' attribute (all marimo widgets have this)
    if not hasattr(obj, "value"):
        return False

    # Check if the type name matches known marimo widget types
    widget_type_names = {
        "slider",
        "range_slider",
        "number",
        "text",
        "checkbox",
        "dropdown",
        "button",
        "date",
        "file",
        "multiselect",
        "radio",
        "switch",
        "textarea",
    }

    type_name = type(obj).__name__
    return type_name in widget_type_names


def get_marimo_annotations(func: Callable[..., Any]) -> dict[str, Any]:
    """Extract marimo widget annotations from a function's type hints.

    This function inspects the type hints of a function and extracts any
    marimo widget instances used with `typing.Annotated`.

    Args:
        func: The function to inspect.

    Returns:
        A dictionary mapping parameter names to their marimo widget instances.

    Example:
        from typing import Annotated
        import marimo as mo

        def my_func(
            x: Annotated[int, mo.ui.slider(start=0, stop=100)],
            y: str,
        ) -> int:
            return x

        annotations = get_marimo_annotations(my_func)
        # annotations = {"x": <marimo.ui.slider widget>}
    """
    try:
        from typing import Annotated, get_type_hints
    except ImportError:
        from typing import Annotated, get_type_hints

    annotations: dict[str, Any] = {}

    # Use get_type_hints to properly resolve string annotations from
    # `from __future__ import annotations`. We include_extras to preserve
    # Annotated metadata.
    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception:
        # Fall back to raw __annotations__ if get_type_hints fails
        hints = getattr(func, "__annotations__", {})

    for param_name, hint in hints.items():
        if param_name == "return":
            continue

        # Check if this is an Annotated type
        origin = get_origin(hint)
        if origin is Annotated:
            args = get_args(hint)
            # args[0] is the base type, args[1:] are the metadata
            for arg in args[1:]:
                # Check for literal marimo widgets
                if _is_marimo_widget(arg):
                    annotations[param_name] = arg
                    break

    return annotations


def get_marimo_widgets(func: Callable[..., Any]) -> Any:
    """Get marimo UI widgets for all annotated parameters of a function.

    This is a convenience function that extracts marimo widget annotations
    and returns them as a marimo.ui.dictionary.

    Args:
        func: The function to get widgets for.

    Returns:
        A marimo.ui.dictionary mapping parameter names to their marimo UI widgets.

    Example:
        from typing import Annotated
        import marimo as mo
        import weave

        @weave.op
        def process_value(
            x: Annotated[int, mo.ui.slider(start=0, stop=100, step=1)]
        ) -> int:
            return x * 2

        widgets = get_marimo_widgets(process_value)
        # widgets is a marimo.ui.dictionary with {"x": <marimo.ui.slider>}
    """
    annotations = get_marimo_annotations(func)
    return mo.ui.dictionary(annotations)


def get_return_marimo_annotation(func: Callable[..., Any]) -> Any | None:
    """Extract the marimo widget annotation from a function's return type.

    Args:
        func: The function to inspect.

    Returns:
        The marimo widget instance for the return type, or None if not present.

    Example:
        from typing import Annotated
        import marimo as mo

        def my_func(x: int) -> Annotated[int, mo.ui.slider(start=0, stop=100)]:
            return x * 2

        annotation = get_return_marimo_annotation(my_func)
        # annotation = <marimo.ui.slider widget>
    """
    try:
        from typing import Annotated, get_type_hints
    except ImportError:
        from typing import Annotated, get_type_hints

    # Use get_type_hints to properly resolve string annotations from
    # `from __future__ import annotations`. We include_extras to preserve
    # Annotated metadata.
    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception:
        # Fall back to raw __annotations__ if get_type_hints fails
        hints = getattr(func, "__annotations__", {})

    return_hint = hints.get("return")

    if return_hint is None:
        return None

    origin = get_origin(return_hint)
    if origin is Annotated:
        args = get_args(return_hint)
        for arg in args[1:]:
            # Check for literal marimo widgets
            if _is_marimo_widget(arg):
                return arg

    return None
