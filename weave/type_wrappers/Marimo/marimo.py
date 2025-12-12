from __future__ import annotations

import contextlib
from collections.abc import Callable, Iterator
from contextvars import ContextVar
from typing import Any, get_args, get_origin
from weakref import WeakKeyDictionary

import marimo as mo

# Cache for widget dictionaries to ensure we return the same instance
# for the same function, preventing duplicate widget registrations in marimo
_widget_cache: WeakKeyDictionary[Callable[..., Any], Any] = WeakKeyDictionary()

# Context variable to store combined widgets for automatic value extraction
_combined_widgets_context: ContextVar[Any | None] = ContextVar(
    "combined_widgets", default=None
)

# Context variable to store control values for variable injection
_control_values_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "control_values", default=None
)


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

    # For weave.op decorated functions, use resolve_fn to get the original function
    # to avoid potential issues with reading annotations from wrappers
    resolve_fn = getattr(func, "resolve_fn", None)
    if resolve_fn is not None:
        func = resolve_fn

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
    and returns them as a marimo.ui.dictionary. The result is cached per function
    to ensure the same dictionary instance is returned, preventing duplicate
    widget registrations in marimo's dependency graph.

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
    # Use resolve_fn for weave.op decorated functions to ensure consistent caching
    resolve_fn = getattr(func, "resolve_fn", None)
    cache_key = resolve_fn if resolve_fn is not None else func

    # Return cached dictionary if available to prevent duplicate widget registrations
    if cache_key in _widget_cache:
        return _widget_cache[cache_key]

    annotations = get_marimo_annotations(func)
    widgets = mo.ui.dictionary(annotations)
    _widget_cache[cache_key] = widgets
    return widgets


def expose_controls(*funcs: Callable[..., Any]) -> Any:
    """Expose marimo UI widget controls from multiple functions in a single dictionary.

    This function extracts widgets from multiple functions and combines them into
    a single marimo.ui.dictionary. This is useful when you want to display controls
    for multiple functions together and pass values to each function separately.

    Args:
        *funcs: Variable number of functions to extract widgets from.

    Returns:
        A marimo.ui.dictionary containing all widgets from all functions.

    Raises:
        ValueError: If there are duplicate parameter names across functions.

    Example:
        from typing import Annotated
        import marimo as mo
        import weave

        @weave.op
        def search(
            model: Annotated[str, mo.ui.dropdown(["gpt-4o-mini"], value="gpt-4o-mini")],
            prompt: Annotated[str, mo.ui.text("Search input")],
        ) -> str:
            return f"{model}: {prompt}"

        @weave.op
        def fan_out(
            limit: Annotated[int, mo.ui.slider(start=1, stop=5, step=1)],
        ) -> list[str]:
            return [search() for _ in range(limit)]

        # Expose controls from both functions
        controls = expose_controls(search, fan_out)
        # controls.value = {"model": "...", "prompt": "...", "limit": 3}

        # Extract values for each function
        search_values = extract_widget_values_for_function(controls, search)
        fan_out_values = extract_widget_values_for_function(controls, fan_out)

        # Use the values
        result = await fan_out(**fan_out_values)
        # Inside fan_out, search() will use default values unless you pass them
    """
    combined_annotations: dict[str, Any] = {}
    func_names: dict[str, list[str]] = {}  # Track which function each param comes from

    for func in funcs:
        annotations = get_marimo_annotations(func)
        func_name = getattr(func, "__name__", str(func))

        for param_name, widget in annotations.items():
            if param_name in combined_annotations:
                # Check if it's the same widget instance (same function, same param)
                if combined_annotations[param_name] is not widget:
                    # Different widget with same name - conflict!
                    raise ValueError(
                        f"Duplicate parameter name '{param_name}' found across functions. "
                        f"Found in: {', '.join(func_names[param_name] + [func_name])}"
                    )
                # Same widget instance - likely same function passed twice, just track it
                if func_name not in func_names[param_name]:
                    func_names[param_name].append(func_name)
            else:
                combined_annotations[param_name] = widget
                func_names[param_name] = [func_name]

    widgets_dict = mo.ui.dictionary(combined_annotations)

    # Return the actual mo.ui.dictionary for proper marimo dependency tracking
    # Wrap it to set context and inject control values when value is accessed
    class _ContextDict:
        """Wrapper that sets context and control values on value access."""

        def __init__(self, d: Any):
            object.__setattr__(self, "_dict", d)

        def __getattribute__(self, name: str) -> Any:
            if name == "value":
                # Set both contexts when value is accessed
                val = object.__getattribute__(self, "_dict").value
                _combined_widgets_context.set(object.__getattribute__(self, "_dict"))
                _control_values_context.set(val)  # Make values available for injection
                return val
            return getattr(object.__getattribute__(self, "_dict"), name)

        def __setattr__(self, name: str, value: Any) -> None:
            if name == "_dict":
                object.__setattr__(self, name, value)
            else:
                setattr(object.__getattribute__(self, "_dict"), name, value)

        def __getattr__(self, name: str) -> Any:
            return getattr(object.__getattribute__(self, "_dict"), name)

    return _ContextDict(widgets_dict)


def extract_widget_values_for_function(
    widgets_or_funcs: Any | list[Callable[..., Any]], func: Callable[..., Any]
) -> Callable[[], dict[str, Any]]:
    """Extract widget values for a specific function from combined widgets.

    This helper function returns a callable that extracts only the values needed
    for a specific function. It can accept either a combined widget dictionary
    or a list of functions (which will be combined internally). The callable
    defers value access to avoid marimo's restriction on accessing widget values
    in the same cell where they were created.

    Args:
        widgets_or_funcs: Either a marimo.ui.dictionary from `expose_controls`,
            or a list of functions to combine widgets from.
        func: The function to extract values for.

    Returns:
        A callable that, when called, returns a dictionary mapping parameter names
        to their current widget values, containing only the parameters that the
        function expects.

    Example:
        # Option 1: Using a list of functions (recommended)
        # In one cell:
        get_search_values = extract_widget_values_for_function([search, fan_out], search)
        get_fan_out_values = extract_widget_values_for_function([search, fan_out], fan_out)
        controls = expose_controls(search, fan_out)  # For display

        # In another cell (to avoid accessing .value in the same cell):
        search_values = get_search_values()
        fan_out_values = get_fan_out_values()
        result = await search(**search_values)
        result2 = await fan_out(**fan_out_values)

        # Option 2: Using pre-combined widgets
        controls = expose_controls(search, fan_out)
        get_search_values = extract_widget_values_for_function(combined_widgets, search)
    """
    # If it's a list, combine the widgets internally
    if isinstance(widgets_or_funcs, list):
        combined_widgets = expose_controls(*widgets_or_funcs)
    else:
        combined_widgets = widgets_or_funcs

    func_annotations = get_marimo_annotations(func)
    param_names = list(func_annotations.keys())

    def get_values() -> dict[str, Any]:
        """Extract values for the function from combined widgets."""
        combined_values = combined_widgets.value
        # Extract only the values for parameters this function expects
        return {
            param_name: combined_values[param_name]
            for param_name in param_names
            if param_name in combined_values
        }

    return get_values


def get_widget_values_for_function(
    widgets_or_funcs: Any | list[Callable[..., Any]], func: Callable[..., Any]
) -> dict[str, Any]:
    """Get widget values for a specific function from combined widgets.

    This is a convenience function that immediately extracts values. Use this
    in a separate marimo cell from where widgets were created to avoid marimo's
    restriction on accessing widget values in the same cell.

    Args:
        widgets_or_funcs: Either a marimo.ui.dictionary from `expose_controls`,
            or a list of functions to combine widgets from.
        func: The function to extract values for.

    Returns:
        A dictionary mapping parameter names to their current widget values,
        containing only the parameters that the function expects.

    Example:
        # Option 1: Using a list of functions (recommended)
        # In cell 1:
        controls = expose_controls(search, fan_out)  # For display

        # In cell 2 (separate cell!):
        search_values = get_widget_values_for_function([search, fan_out], search)
        fan_out_values = get_widget_values_for_function([search, fan_out], fan_out)
        result = await fan_out(**fan_out_values)

        # Option 2: Using pre-combined widgets
        controls = expose_controls(search, fan_out)
        search_values = get_widget_values_for_function(combined_widgets, search)
    """
    # If it's a list, combine the widgets internally
    if isinstance(widgets_or_funcs, list):
        combined_widgets = expose_controls(*widgets_or_funcs)
    else:
        combined_widgets = widgets_or_funcs

    func_annotations = get_marimo_annotations(func)
    combined_values = combined_widgets.value

    # Extract only the values for parameters this function expects
    return {
        param_name: combined_values[param_name]
        for param_name in func_annotations.keys()
        if param_name in combined_values
    }


@contextlib.contextmanager
def with_widgets(widgets_or_funcs: Any | list[Callable[..., Any]]) -> Iterator[Any]:
    """Context manager that makes widget values available to functions.

    Within this context, functions can call `get_widget_values()` to automatically
    get their widget values without needing to pass widgets around.

    Args:
        widgets_or_funcs: Either a marimo.ui.dictionary from `expose_controls`,
            or a list of functions to combine widgets from.

    Example:
        # In cell 1:
        controls = expose_controls(search, fan_out)

        # In cell 2:
        with with_widgets(combined_widgets):
            # Now functions can use get_widget_values() internally
            result = await fan_out(**get_widget_values_for_current_context(fan_out))
    """
    # Resolve widgets
    if isinstance(widgets_or_funcs, list):
        combined_widgets = expose_controls(*widgets_or_funcs)
    else:
        combined_widgets = widgets_or_funcs

    token = _combined_widgets_context.set(combined_widgets)
    try:
        yield combined_widgets
    finally:
        _combined_widgets_context.reset(token)


def get_widget_values_for_current_context(func: Callable[..., Any]) -> dict[str, Any]:
    """Get widget values for a function from the current context.

    This function extracts widget values for the given function from widgets
    set in the current `with_widgets()` context. This allows functions to access
    widget values without needing them passed as parameters.

    Args:
        func: The function to extract values for.

    Returns:
        A dictionary mapping parameter names to their current widget values.

    Raises:
        RuntimeError: If called outside a `with_widgets()` context.

    Example:
        @weave.op
        async def fan_out(limit: ...) -> list[str]:
            # Get search values from context - no need to pass widgets!
            search_values = get_widget_values_for_current_context(search)
            async with asyncio.TaskGroup() as tg:
                tasks = [tg.create_task(search(**search_values)) for _ in range(limit)]
            return [t.result() for t in tasks]

        # Usage:
        with with_widgets([search, fan_out]):
            result = await fan_out(**get_widget_values_for_current_context(fan_out))
    """
    combined_widgets = _combined_widgets_context.get()
    if combined_widgets is None:
        raise RuntimeError(
            "get_widget_values_for_current_context() must be called within "
            "a 'with_widgets()' context manager"
        )
    return get_widget_values_for_function(combined_widgets, func)


def auto_widget(func: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap a function to automatically use widget values when called without arguments.

    This wrapper allows a function to be called without arguments, and it will
    automatically extract widget values from the current `with_widgets()` context.
    If arguments are provided, they override the widget values.

    Args:
        func: The function to wrap.

    Returns:
        A wrapped function that can be called with or without arguments.

    Example:
        @weave.op
        async def search(
            model: Annotated[str, mo.ui.dropdown(...)],
            prompt: Annotated[str, mo.ui.text(...)],
        ) -> str:
            ...

        @weave.op
        async def fan_out(limit: Annotated[int, mo.ui.slider(...)]) -> list[str]:
            # Wrap search to auto-use widget values
            auto_search = auto_widget(search)

            # Can call without arguments - uses widget values automatically
            async with asyncio.TaskGroup() as tg:
                tasks = [tg.create_task(auto_search()) for _ in range(limit)]
            return [t.result() for t in tasks]

        # Usage:
        with with_widgets([search, fan_out]):
            result = await fan_out(**get_widget_values_for_current_context(fan_out))
    """
    import inspect
    from functools import wraps

    is_async = inspect.iscoroutinefunction(func)

    if is_async:

        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # If no arguments provided, try to get widget values from context
            if not args and not kwargs:
                try:
                    widget_values = get_widget_values_for_current_context(func)
                    return await func(**widget_values)
                except RuntimeError:
                    # No context available, call with no args (will use defaults)
                    return await func()
            else:
                # Arguments provided, use them (they override widget values)
                return await func(*args, **kwargs)

        return async_wrapper
    else:

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # If no arguments provided, try to get widget values from context
            if not args and not kwargs:
                try:
                    widget_values = get_widget_values_for_current_context(func)
                    return func(**widget_values)
                except RuntimeError:
                    # No context available, call with no args (will use defaults)
                    return func()
            else:
                # Arguments provided, use them (they override widget values)
                return func(*args, **kwargs)

        return wrapper


class _ControlResolver:
    """Special object that resolves control values when accessed as attributes.

    Usage:
        from weave.type_wrappers.Marimo import control

        @weave.op
        async def fan_out(limit: ...) -> list[str]:
            model = control.model  # Gets value from controls
            prompt = control.prompt  # Gets value from controls
            # Use model and prompt...
    """

    def __getattr__(self, name: str) -> Any:
        """Resolve control value by name."""
        control_values = _control_values_context.get()
        if control_values is None:
            raise RuntimeError(
                f"control.{name} must be used within a cell that "
                "accesses controls.value (e.g., controls = expose_controls(...); controls.value)"
            )
        if name not in control_values:
            raise AttributeError(
                f"Control '{name}' not found in controls. "
                f"Available controls: {list(control_values.keys())}"
            )
        return control_values[name]

    def __repr__(self) -> str:
        return "control"


# Global instance for easy access
control = _ControlResolver()


def control_value(name: str) -> Any:
    """Get a control value by name from the current controls context.

    This function retrieves values from controls created by `expose_controls`.
    It must be called within a cell that has accessed `controls.value` to set
    the context.

    Args:
        name: The name of the control to retrieve.

    Returns:
        The current value of the control.

    Raises:
        RuntimeError: If called outside a controls context.
        KeyError: If the control name is not found.

    Example:
        @weave.op
        async def fan_out(limit: Annotated[int, mo.ui.slider(...)]) -> list[str]:
            model = control_value('model')  # Gets from controls
            prompt = control_value('prompt')  # Gets from controls
            async with asyncio.TaskGroup() as tg:
                tasks = [tg.create_task(search(model, prompt)) for _ in range(limit)]
            return [t.result() for t in tasks]

        # In a cell:
        controls = expose_controls(search, fan_out)
        controls.value  # This sets the context
        await fan_out(controls.value['limit'])
    """
    control_values = _control_values_context.get()
    if control_values is None:
        raise RuntimeError(
            f"control_value('{name}') must be used within a cell that "
            "accesses controls.value (e.g., controls = expose_controls(...); controls.value)"
        )
    if name not in control_values:
        raise KeyError(
            f"Control '{name}' not found in controls. "
            f"Available controls: {list(control_values.keys())}"
        )
    return control_values[name]


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

    # For weave.op decorated functions, use resolve_fn to get the original function
    # to avoid potential issues with reading annotations from wrappers
    resolve_fn = getattr(func, "resolve_fn", None)
    if resolve_fn is not None:
        func = resolve_fn

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
