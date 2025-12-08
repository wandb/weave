from __future__ import annotations

from typing import Annotated

import pytest

import weave
from weave.type_wrappers.Marimo import (
    Marimo,
    get_marimo_annotations,
    get_marimo_widgets,
    get_return_marimo_annotation,
)


class TestMarimoAnnotation:
    def test_marimo_slider_annotation_basic(self):
        """Test basic Marimo slider annotation creation."""
        marimo = Marimo(type="slider", start=0, stop=100)
        assert marimo.type == "slider"
        assert marimo.start == 0
        assert marimo.stop == 100
        assert marimo.step is None
        assert marimo.value is None

    def test_marimo_slider_annotation_full(self):
        """Test Marimo slider with all options."""
        marimo = Marimo(
            type="slider",
            start=0,
            stop=100,
            step=5,
            value=50,
            label="My Slider",
            debounce=True,
            show_value=False,
        )
        assert marimo.type == "slider"
        assert marimo.start == 0
        assert marimo.stop == 100
        assert marimo.step == 5
        assert marimo.value == 50
        assert marimo.label == "My Slider"
        assert marimo.debounce is True
        assert marimo.show_value is False

    def test_marimo_text_annotation(self):
        """Test Marimo text annotation."""
        marimo = Marimo(type="text", placeholder="Enter text here")
        assert marimo.type == "text"
        assert marimo.placeholder == "Enter text here"

    def test_marimo_checkbox_annotation(self):
        """Test Marimo checkbox annotation."""
        marimo = Marimo(type="checkbox", value=True, label="Enable feature")
        assert marimo.type == "checkbox"
        assert marimo.value is True
        assert marimo.label == "Enable feature"

    def test_marimo_dropdown_annotation(self):
        """Test Marimo dropdown annotation."""
        marimo = Marimo(
            type="dropdown", options=["option1", "option2", "option3"], value="option1"
        )
        assert marimo.type == "dropdown"
        assert marimo.options == ["option1", "option2", "option3"]
        assert marimo.value == "option1"

    def test_marimo_number_annotation(self):
        """Test Marimo number annotation."""
        marimo = Marimo(type="number", start=0, stop=10, step=0.1, value=5.0)
        assert marimo.type == "number"
        assert marimo.start == 0
        assert marimo.stop == 10
        assert marimo.step == 0.1
        assert marimo.value == 5.0

    def test_marimo_range_slider_annotation(self):
        """Test Marimo range slider annotation."""
        marimo = Marimo(type="range_slider", start=0, stop=100, value=[25, 75])
        assert marimo.type == "range_slider"
        assert marimo.start == 0
        assert marimo.stop == 100
        assert marimo.value == [25, 75]


class TestMarimoExtractionFromFunction:
    def test_get_marimo_annotations_single(self):
        """Test extracting a single Marimo annotation from function."""

        def my_func(
            x: Annotated[int, Marimo(type="slider", start=0, stop=100)]
        ) -> int:
            return x * 2

        annotations = get_marimo_annotations(my_func)
        assert "x" in annotations
        assert annotations["x"].type == "slider"
        assert annotations["x"].start == 0
        assert annotations["x"].stop == 100

    def test_get_marimo_annotations_multiple(self):
        """Test extracting multiple Marimo annotations from function."""

        def my_func(
            x: Annotated[int, Marimo(type="slider", start=0, stop=100)],
            y: Annotated[float, Marimo(type="number", start=0.0, stop=1.0, step=0.1)],
            z: str,  # No annotation
        ) -> int:
            return int(x + y)

        annotations = get_marimo_annotations(my_func)
        assert len(annotations) == 2
        assert "x" in annotations
        assert "y" in annotations
        assert "z" not in annotations

    def test_get_marimo_annotations_no_annotations(self):
        """Test function with no Marimo annotations."""

        def my_func(x: int, y: float) -> int:
            return int(x + y)

        annotations = get_marimo_annotations(my_func)
        assert len(annotations) == 0

    def test_get_marimo_annotations_with_weave_op(self):
        """Test extracting Marimo annotations from weave.op decorated function."""

        @weave.op
        def process_value(
            x: Annotated[int, Marimo(type="slider", start=0, stop=100, step=1)]
        ) -> int:
            return x * 2

        # weave.op wraps the function, so we need to access the original
        annotations = get_marimo_annotations(process_value)
        assert "x" in annotations
        assert annotations["x"].type == "slider"

    def test_get_return_marimo_annotation(self):
        """Test extracting Marimo annotation from return type."""

        def my_func(
            x: int,
        ) -> Annotated[int, Marimo(type="slider", start=0, stop=100)]:
            return x * 2

        annotation = get_return_marimo_annotation(my_func)
        assert annotation is not None
        assert annotation.type == "slider"
        assert annotation.start == 0
        assert annotation.stop == 100

    def test_get_return_marimo_annotation_none(self):
        """Test function with no return Marimo annotation."""

        def my_func(x: int) -> int:
            return x * 2

        annotation = get_return_marimo_annotation(my_func)
        assert annotation is None


class TestMarimoWidgetCreation:
    """Tests that require marimo to be installed."""

    @pytest.fixture
    def skip_if_no_marimo(self):
        """Skip test if marimo is not installed."""
        try:
            import marimo  # noqa: F401
        except ImportError:
            pytest.skip("marimo is not installed")

    def test_to_widget_slider_missing_params(self):
        """Test that slider raises error without start/stop."""
        try:
            import marimo  # noqa: F401
        except ImportError:
            pytest.skip("marimo is not installed")

        marimo_annotation = Marimo(type="slider")
        with pytest.raises(ValueError, match="Slider requires 'start' and 'stop'"):
            marimo_annotation.to_widget()

    def test_to_widget_dropdown_missing_options(self):
        """Test that dropdown raises error without options."""
        try:
            import marimo  # noqa: F401
        except ImportError:
            pytest.skip("marimo is not installed")

        marimo_annotation = Marimo(type="dropdown")
        with pytest.raises(ValueError, match="Dropdown requires 'options'"):
            marimo_annotation.to_widget()

    def test_to_widget_slider_creates_widget(self):
        """Test that slider creates a marimo.ui.slider widget."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        marimo_annotation = Marimo(type="slider", start=0, stop=100, step=1)
        widget = marimo_annotation.to_widget()
        assert hasattr(widget, "value")
        # Check it's a slider type
        assert type(widget).__name__ == "slider"

    def test_to_widget_text_creates_widget(self):
        """Test that text creates a marimo.ui.text widget."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        marimo_annotation = Marimo(type="text", placeholder="Enter text")
        widget = marimo_annotation.to_widget()
        assert hasattr(widget, "value")
        assert type(widget).__name__ == "text"

    def test_to_widget_checkbox_creates_widget(self):
        """Test that checkbox creates a marimo.ui.checkbox widget."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        marimo_annotation = Marimo(type="checkbox", value=True)
        widget = marimo_annotation.to_widget()
        assert hasattr(widget, "value")
        assert type(widget).__name__ == "checkbox"

    def test_to_widget_number_creates_widget(self):
        """Test that number creates a marimo.ui.number widget."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        marimo_annotation = Marimo(type="number", start=0, stop=10)
        widget = marimo_annotation.to_widget()
        assert hasattr(widget, "value")
        assert type(widget).__name__ == "number"

    def test_to_widget_dropdown_creates_widget(self):
        """Test that dropdown creates a marimo.ui.dropdown widget."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        marimo_annotation = Marimo(
            type="dropdown", options=["a", "b", "c"], value="a"
        )
        widget = marimo_annotation.to_widget()
        assert hasattr(widget, "value")
        assert type(widget).__name__ == "dropdown"

    def test_get_marimo_widgets(self):
        """Test get_marimo_widgets creates all widgets for a function."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        def my_func(
            x: Annotated[int, Marimo(type="slider", start=0, stop=100)],
            y: Annotated[str, Marimo(type="text", placeholder="Enter")],
        ) -> int:
            return x

        widgets = get_marimo_widgets(my_func)
        assert "x" in widgets
        assert "y" in widgets
        assert type(widgets["x"]).__name__ == "slider"
        assert type(widgets["y"]).__name__ == "text"


class TestMarimoImportability:
    def test_import_from_weave(self):
        """Test that Marimo can be imported from weave."""
        from weave import Marimo

        assert Marimo is not None

    def test_import_from_type_wrappers(self):
        """Test that Marimo can be imported from type_wrappers."""
        from weave.type_wrappers import Marimo

        assert Marimo is not None

    def test_in_weave_all(self):
        """Test that Marimo is in weave.__all__."""
        import weave

        assert "Marimo" in weave.__all__
