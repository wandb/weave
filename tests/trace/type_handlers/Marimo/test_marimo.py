from __future__ import annotations

from typing import Annotated

import pytest

import weave
from weave.type_wrappers.Marimo import (
    get_marimo_annotations,
    get_marimo_widgets,
    get_return_marimo_annotation,
)


class TestMarimoExtractionFromFunction:
    def test_get_marimo_annotations_single(self):
        """Test extracting a single literal marimo widget annotation from function."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        def my_func(
            x: Annotated[int, mo.ui.slider(start=0, stop=100)]
        ) -> int:
            return x * 2

        annotations = get_marimo_annotations(my_func)
        assert "x" in annotations
        # Should be a literal widget instance
        assert hasattr(annotations["x"], "value")
        assert type(annotations["x"]).__name__ == "slider"

    def test_get_marimo_annotations_multiple(self):
        """Test extracting multiple literal marimo widget annotations from function."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        def my_func(
            x: Annotated[int, mo.ui.slider(start=0, stop=100)],
            y: Annotated[float, mo.ui.number(start=0.0, stop=1.0, step=0.1)],
            z: str,  # No annotation
        ) -> int:
            return int(x + y)

        annotations = get_marimo_annotations(my_func)
        assert len(annotations) == 2
        assert "x" in annotations
        assert "y" in annotations
        assert "z" not in annotations
        # Should be literal widget instances
        assert hasattr(annotations["x"], "value")
        assert hasattr(annotations["y"], "value")
        assert type(annotations["x"]).__name__ == "slider"
        assert type(annotations["y"]).__name__ == "number"

    def test_get_marimo_annotations_no_annotations(self):
        """Test function with no Marimo annotations."""

        def my_func(x: int, y: float) -> int:
            return int(x + y)

        annotations = get_marimo_annotations(my_func)
        assert len(annotations) == 0

    def test_get_marimo_annotations_with_weave_op(self):
        """Test extracting marimo widget annotations from weave.op decorated function."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        @weave.op
        def process_value(
            x: Annotated[int, mo.ui.slider(start=0, stop=100, step=1)]
        ) -> int:
            return x * 2

        # weave.op wraps the function, so we need to access the original
        annotations = get_marimo_annotations(process_value)
        assert "x" in annotations
        assert hasattr(annotations["x"], "value")
        assert type(annotations["x"]).__name__ == "slider"

    def test_get_return_marimo_annotation(self):
        """Test extracting literal marimo widget annotation from return type."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        def my_func(
            x: int,
        ) -> Annotated[int, mo.ui.slider(start=0, stop=100)]:
            return x * 2

        annotation = get_return_marimo_annotation(my_func)
        assert annotation is not None
        # Should be a literal widget instance
        assert hasattr(annotation, "value")
        assert type(annotation).__name__ == "slider"

    def test_get_return_marimo_annotation_none(self):
        """Test function with no return Marimo annotation."""

        def my_func(x: int) -> int:
            return x * 2

        annotation = get_return_marimo_annotation(my_func)
        assert annotation is None


class TestMarimoWidgetCreation:
    """Tests that require marimo to be installed."""

    def test_get_marimo_widgets(self):
        """Test get_marimo_widgets with literal marimo widgets."""
        try:
            import marimo as mo
        except ImportError:
            pytest.skip("marimo is not installed")

        def my_func(
            x: Annotated[int, mo.ui.slider(start=0, stop=100)],
            y: Annotated[str, mo.ui.text(placeholder="Enter")],
        ) -> int:
            return x

        widgets = get_marimo_widgets(my_func)
        assert "x" in widgets
        assert "y" in widgets
        assert type(widgets["x"]).__name__ == "slider"
        assert type(widgets["y"]).__name__ == "text"


