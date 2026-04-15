"""Unit tests for weave.integrations.wandb.media — _unwrap_value.

Tests do not require a running Weave client. wandb is imported via
pytest.importorskip so the entire module is skipped when wandb is not installed.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from weave.integrations.wandb.media import _unwrap_value

wandb = pytest.importorskip("wandb")


# ---------------------------------------------------------------------------
# Fake wandb media subclasses
# ---------------------------------------------------------------------------
# These bypass the complex wandb media __init__ so tests don't need real files
# for the PIL path; the path-fallback tests use real temp files.


class _FakeImage(wandb.Image):
    def __init__(self, path: str, pil_image: object = None) -> None:
        object.__init__(self)
        self._path = path
        self._pil_image = pil_image

    @property
    def image(self) -> object:
        return self._pil_image


# ---------------------------------------------------------------------------
# Scalar passthrough
# ---------------------------------------------------------------------------


def test_scalar_passthrough():
    """Non-media values are returned unchanged."""
    warned: set[type] = set()
    assert _unwrap_value("cat", "col", warned) == "cat"
    assert _unwrap_value(42, "col", warned) == 42
    assert _unwrap_value(True, "col", warned) is True
    assert _unwrap_value(None, "col", warned) is None


# ---------------------------------------------------------------------------
# wandb.Image conversion
# ---------------------------------------------------------------------------


def test_image_converted_to_pil_when_available():
    """When _FakeImage provides a PIL image, it is returned directly."""
    pil_module = pytest.importorskip("PIL.Image")
    pil_img = pil_module.new("RGB", (1, 1))
    img = _FakeImage("/fake/cat.png", pil_image=pil_img)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = _unwrap_value(img, "image", set())

    assert result is pil_img
    assert any("wandb.Image" in str(w.message) for w in caught)


def test_image_falls_back_to_content_when_no_pil(tmp_path: Path):
    """When .image is None, falls back to Content.from_path()."""
    from weave.type_wrappers.Content.content import Content

    img_file = tmp_path / "cat.png"
    img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)
    img = _FakeImage(str(img_file), pil_image=None)

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = _unwrap_value(img, "image", set())

    assert isinstance(result, Content)


def test_image_warning_emitted_only_once():
    """The wandb.Image warning fires once per shared warned set, not per call."""
    pil_module = pytest.importorskip("PIL.Image")
    pil_img = pil_module.new("RGB", (1, 1))
    warned: set[type] = set()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for i in range(5):
            _unwrap_value(_FakeImage(f"/img/{i}.png", pil_image=pil_img), "image", warned)

    image_warnings = [w for w in caught if "wandb.Image" in str(w.message)]
    assert len(image_warnings) == 1


# ---------------------------------------------------------------------------
# Unsupported media type
# ---------------------------------------------------------------------------


def test_unsupported_media_raises_type_error():
    """A wandb Media subclass that isn't wandb.Image raises TypeError."""
    from wandb.sdk.data_types.base_types.media import Media as _WandbMedia

    class _FakeUnsupported(_WandbMedia):
        _log_type = "fake-unsupported"

        def __init__(self) -> None:
            object.__init__(self)

    with pytest.raises(TypeError, match="Unsupported wandb media type"):
        _unwrap_value(_FakeUnsupported(), "col", set())
