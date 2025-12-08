from __future__ import annotations

from typing import Any, Callable, Literal, get_args, get_origin

from pydantic import BaseModel


class Marimo(BaseModel):
    """A type annotation wrapper for specifying Marimo UI widgets.

    Use this class with `typing.Annotated` to specify how a function parameter
    should be rendered as a Marimo UI widget.

    Example:
        from typing import Annotated
        import weave
        from weave.type_wrappers import Marimo

        @weave.op
        def process_value(
            x: Annotated[int, Marimo(type="slider", start=0, stop=100, step=1)]
        ) -> int:
            return x * 2

        # Later, when creating the Marimo UI:
        marimo_annotation = Marimo(type="slider", start=0, stop=100, step=1)
        slider_widget = marimo_annotation.to_widget()
    """

    type: Literal["slider", "range_slider", "number", "text", "checkbox", "dropdown"]
    """The type of Marimo UI widget to create."""

    # Slider-specific options
    start: float | int | None = None
    """Minimum value for slider widgets."""

    stop: float | int | None = None
    """Maximum value for slider widgets."""

    step: float | int | None = None
    """Step increment for slider widgets."""

    value: Any = None
    """Default/initial value for the widget."""

    # Common options
    label: str | None = None
    """Label to display for the widget."""

    debounce: bool = False
    """Only emit changes on release (for sliders)."""

    show_value: bool = True
    """Whether to display the current value."""

    # Dropdown-specific options
    options: list[str] | dict[str, Any] | None = None
    """Options for dropdown widgets."""

    # Text-specific options
    placeholder: str | None = None
    """Placeholder text for text inputs."""

    def to_widget(self) -> Any:
        """Create and return the corresponding marimo.ui widget.

        Returns:
            A marimo UI widget instance based on the configured type.

        Raises:
            ImportError: If marimo is not installed.
            ValueError: If required parameters are missing for the widget type.
        """
        try:
            import marimo as mo
        except ImportError as e:
            raise ImportError(
                "marimo is required to create widgets. Install it with: pip install marimo"
            ) from e

        if self.type == "slider":
            return self._create_slider(mo)
        elif self.type == "range_slider":
            return self._create_range_slider(mo)
        elif self.type == "number":
            return self._create_number(mo)
        elif self.type == "text":
            return self._create_text(mo)
        elif self.type == "checkbox":
            return self._create_checkbox(mo)
        elif self.type == "dropdown":
            return self._create_dropdown(mo)
        else:
            raise ValueError(f"Unknown widget type: {self.type}")

    def _create_slider(self, mo: Any) -> Any:
        """Create a marimo.ui.slider widget."""
        if self.start is None or self.stop is None:
            raise ValueError("Slider requires 'start' and 'stop' parameters")

        kwargs: dict[str, Any] = {
            "start": self.start,
            "stop": self.stop,
            "debounce": self.debounce,
            "show_value": self.show_value,
        }

        if self.step is not None:
            kwargs["step"] = self.step
        if self.value is not None:
            kwargs["value"] = self.value
        if self.label is not None:
            kwargs["label"] = self.label

        return mo.ui.slider(**kwargs)

    def _create_range_slider(self, mo: Any) -> Any:
        """Create a marimo.ui.range_slider widget."""
        if self.start is None or self.stop is None:
            raise ValueError("Range slider requires 'start' and 'stop' parameters")

        kwargs: dict[str, Any] = {
            "start": self.start,
            "stop": self.stop,
            "debounce": self.debounce,
            "show_value": self.show_value,
        }

        if self.step is not None:
            kwargs["step"] = self.step
        if self.value is not None:
            kwargs["value"] = self.value
        if self.label is not None:
            kwargs["label"] = self.label

        return mo.ui.range_slider(**kwargs)

    def _create_number(self, mo: Any) -> Any:
        """Create a marimo.ui.number widget."""
        kwargs: dict[str, Any] = {}

        if self.start is not None:
            kwargs["start"] = self.start
        if self.stop is not None:
            kwargs["stop"] = self.stop
        if self.step is not None:
            kwargs["step"] = self.step
        if self.value is not None:
            kwargs["value"] = self.value
        if self.label is not None:
            kwargs["label"] = self.label

        return mo.ui.number(**kwargs)

    def _create_text(self, mo: Any) -> Any:
        """Create a marimo.ui.text widget."""
        kwargs: dict[str, Any] = {}

        if self.value is not None:
            kwargs["value"] = self.value
        if self.label is not None:
            kwargs["label"] = self.label
        if self.placeholder is not None:
            kwargs["placeholder"] = self.placeholder

        return mo.ui.text(**kwargs)

    def _create_checkbox(self, mo: Any) -> Any:
        """Create a marimo.ui.checkbox widget."""
        kwargs: dict[str, Any] = {}

        if self.value is not None:
            kwargs["value"] = self.value
        if self.label is not None:
            kwargs["label"] = self.label

        return mo.ui.checkbox(**kwargs)

    def _create_dropdown(self, mo: Any) -> Any:
        """Create a marimo.ui.dropdown widget."""
        if self.options is None:
            raise ValueError("Dropdown requires 'options' parameter")

        kwargs: dict[str, Any] = {"options": self.options}

        if self.value is not None:
            kwargs["value"] = self.value
        if self.label is not None:
            kwargs["label"] = self.label

        return mo.ui.dropdown(**kwargs)


def get_marimo_annotations(func: Callable[..., Any]) -> dict[str, Marimo]:
    """Extract Marimo annotations from a function's type hints.

    This function inspects the type hints of a function and extracts any
    `Marimo` instances used with `typing.Annotated`.

    Args:
        func: The function to inspect.

    Returns:
        A dictionary mapping parameter names to their Marimo annotations.

    Example:
        from typing import Annotated
        from weave.type_wrappers import Marimo

        def my_func(
            x: Annotated[int, Marimo(type="slider", start=0, stop=100)],
            y: str,
        ) -> int:
            return x

        annotations = get_marimo_annotations(my_func)
        # annotations = {"x": Marimo(type="slider", start=0, stop=100)}
    """
    try:
        from typing import Annotated, get_type_hints
    except ImportError:
        from typing_extensions import Annotated, get_type_hints

    annotations: dict[str, Marimo] = {}

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
                if isinstance(arg, Marimo):
                    annotations[param_name] = arg
                    break

    return annotations


def get_marimo_widgets(func: Callable[..., Any]) -> dict[str, Any]:
    """Create Marimo UI widgets for all annotated parameters of a function.

    This is a convenience function that extracts Marimo annotations and
    creates the corresponding UI widgets.

    Args:
        func: The function to create widgets for.

    Returns:
        A dictionary mapping parameter names to their Marimo UI widgets.

    Example:
        from typing import Annotated
        import weave
        from weave.type_wrappers import Marimo

        @weave.op
        def process_value(
            x: Annotated[int, Marimo(type="slider", start=0, stop=100, step=1)]
        ) -> int:
            return x * 2

        widgets = get_marimo_widgets(process_value)
        # widgets = {"x": <marimo.ui.slider>}
    """
    annotations = get_marimo_annotations(func)
    return {name: marimo.to_widget() for name, marimo in annotations.items()}


def get_return_marimo_annotation(func: Callable[..., Any]) -> Marimo | None:
    """Extract the Marimo annotation from a function's return type.

    Args:
        func: The function to inspect.

    Returns:
        The Marimo annotation for the return type, or None if not present.

    Example:
        from typing import Annotated
        from weave.type_wrappers import Marimo

        def my_func(x: int) -> Annotated[int, Marimo(type="slider", start=0, stop=100)]:
            return x * 2

        annotation = get_return_marimo_annotation(my_func)
        # annotation = Marimo(type="slider", start=0, stop=100)
    """
    try:
        from typing import Annotated, get_type_hints
    except ImportError:
        from typing_extensions import Annotated, get_type_hints

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
            if isinstance(arg, Marimo):
                return arg

    return None
