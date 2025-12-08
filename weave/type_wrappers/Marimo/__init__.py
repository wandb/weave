"""Marimo integration for exposing UI controls from weave.op decorated functions."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
    import marimo as mo

# Check if marimo is available
try:
    import marimo as mo
except ImportError:
    mo = None  # type: ignore


def _extract_marimo_widgets(func: Callable) -> dict[str, Any]:
    """Extract marimo UI widgets from a function's Annotated parameters.

    Args:
        func: Function to inspect for marimo UI widgets.

    Returns:
        Dictionary mapping parameter names to marimo UI widgets.

    Examples:
        >>> @weave.op
        ... def my_func(
        ...     x: Annotated[int, mo.ui.slider(start=0, stop=100)]
        ... ) -> int:
        ...     return x
        >>> widgets = _extract_marimo_widgets(my_func)
        >>> 'x' in widgets
        True
    """
    if mo is None:
        raise ImportError(
            "marimo is not installed. Install it with: pip install marimo"
        )

    widgets: dict[str, Any] = {}

    # Get function signature and type hints
    sig = inspect.signature(func)
    type_hints = get_type_hints(func, include_extras=True)

    for param_name in sig.parameters:
        annotation = type_hints.get(param_name)

        if annotation is None:
            continue

        # Check if this is an Annotated type
        origin = get_origin(annotation)

        if (
            origin is None
            or not hasattr(origin, "__name__")
            or origin.__name__ != "Annotated"
        ):
            continue

        # Extract the annotation arguments
        args = get_args(annotation)
        if not args:
            continue

        # The first arg is the base type, the rest are metadata
        # We're looking for marimo UI widgets in the metadata
        base_type = args[0]
        metadata = args[1:]

        # Check each metadata item to see if it's a marimo UI widget
        for meta_item in metadata:
            # Check if this looks like a marimo UI widget
            # Marimo widgets are instances with a 'value' attribute
            # or have a module name containing 'marimo'
            is_marimo_widget = (
                hasattr(meta_item, "__module__")
                and meta_item.__module__ is not None
                and "marimo" in meta_item.__module__
            )

            if hasattr(meta_item, "value") and is_marimo_widget:
                # This is a marimo widget instance - use it directly
                widgets[param_name] = meta_item
                break
            elif is_marimo_widget:
                # This might be a widget class or instance from marimo
                widgets[param_name] = meta_item
                break

    return widgets


def expose_controls(*funcs: Callable) -> Any:
    """Expose UI controls from one or more weave.op decorated functions.

    This function extracts marimo UI widgets from Annotated parameters in the
    provided functions and returns a mo.ui.dictionary widget that provides access to
    all widget values.

    Args:
        *funcs: One or more functions decorated with @weave.op that have
            Annotated parameters with marimo UI widgets.

    Returns:
        mo.ui.dictionary widget with a .value property that provides access to
        widget values by parameter name.

    Raises:
        ImportError: If marimo is not installed.

    Examples:
        >>> @weave.op
        ... def search(
        ...     model: Annotated[str, mo.ui.dropdown(["a", "b"])],
        ...     prompt: Annotated[str, mo.ui.text()]
        ... ) -> str:
        ...     return f"{model}: {prompt}"
        >>>
        >>> @weave.op
        ... def fan_out(limit: Annotated[int, mo.ui.slider(start=1, stop=5)]) -> list[str]:
        ...     return ["result"] * limit
        >>>
        >>> controls = expose_controls(search, fan_out)
        >>> # Display controls in marimo cell
        >>> controls
        >>> # Access widget values
        >>> model_value = controls.value['model']
        >>> limit_value = controls.value['limit']
    """
    if mo is None:
        raise ImportError(
            "marimo is not installed. Install it with: pip install marimo"
        )

    all_widgets: dict[str, Any] = {}
    func_widget_map: dict[Callable, dict[str, Any]] = {}

    for func in funcs:
        # If the function is wrapped by weave.op, we need to get the original function
        # Check if it has a resolve_fn attribute (common in weave.op)
        actual_func: Callable = func
        if hasattr(func, "resolve_fn"):
            actual_func = func.resolve_fn  # type: ignore
        elif hasattr(func, "__wrapped__"):
            actual_func = func.__wrapped__  # type: ignore

        widgets = _extract_marimo_widgets(actual_func)
        func_widget_map[func] = widgets

        # Check for name conflicts
        for param_name in widgets:
            if param_name in all_widgets:
                raise ValueError(
                    f"Parameter name '{param_name}' appears in multiple functions. "
                    "Consider renaming parameters to avoid conflicts."
                )

        all_widgets.update(widgets)

    # Create dictionary widget - this should properly track all widget states
    # The dictionary widget will handle reactivity for all contained widgets
    controls_dict = mo.ui.dictionary(all_widgets)

    # Patch each function to use widget values from controls
    for func in funcs:
        widgets = func_widget_map[func]

        # For weave.op functions, patch resolve_fn to inject widget values
        if hasattr(func, "resolve_fn"):
            original_resolve_fn = func.resolve_fn  # type: ignore

            def make_patched_resolve_fn(orig_fn: Any, w: dict[str, Any]) -> Any:
                @wraps(orig_fn)
                def patched_resolve_fn(*args: Any, **kwargs: Any) -> Any:
                    # Get widget values from controls dictionary
                    widget_values = controls_dict.value

                    # Get function signature to map positional args to parameter names
                    sig = inspect.signature(orig_fn)
                    param_names = list(sig.parameters.keys())

                    # Convert positional args to kwargs so we can override with widget values
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    # Convert to dict so we can override with widget values
                    all_kwargs = dict(bound_args.arguments)

                    # Override with widget values for parameters that have widgets
                    for param_name in w:
                        if param_name in widget_values:
                            # Always use widget values, overriding any explicit arguments
                            all_kwargs[param_name] = widget_values[param_name]

                    # Call the original function with all kwargs
                    return orig_fn(**all_kwargs)  # type: ignore

                return patched_resolve_fn

            # Replace resolve_fn with the patched version
            func.resolve_fn = make_patched_resolve_fn(original_resolve_fn, widgets)  # type: ignore
        else:
            # For regular functions, wrap the function itself
            original_func = func

            def make_patched_func(
                f: Callable[..., Any], w: dict[str, Any]
            ) -> Callable[..., Any]:
                @wraps(f)
                def patched_func(*args: Any, **kwargs: Any) -> Any:
                    # Get widget values from controls dictionary
                    widget_values = controls_dict.value

                    # Get function signature to map positional args to parameter names
                    sig = inspect.signature(f)
                    param_names = list(sig.parameters.keys())

                    # Convert positional args to kwargs so we can override with widget values
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()
                    # Convert to dict so we can override with widget values
                    all_kwargs = dict(bound_args.arguments)

                    # Override with widget values for parameters that have widgets
                    for param_name in w:
                        if param_name in widget_values:
                            # Always use widget values, overriding any explicit arguments
                            all_kwargs[param_name] = widget_values[param_name]

                    # Call the original function with all kwargs
                    return f(**all_kwargs)

                return patched_func

            # Store the patched version - users would need to use func._marimo_patched
            # or we could try to replace the function in the module, but that's complex
            func._marimo_patched = make_patched_func(original_func, widgets)  # type: ignore

    return controls_dict
