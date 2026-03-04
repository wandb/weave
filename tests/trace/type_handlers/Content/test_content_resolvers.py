"""Tests for MIME type and extension detection via python-magic and polyfile resolvers.

These tests verify that both magic backends produce consistent results for
MIME detection across common media types, and that the resolver dispatch in
utils.py correctly selects and delegates to the available backend.

Each test is parametrized to run under three resolver configurations:
  - python_magic: only python-magic is available
  - polyfile: only polyfile is available
  - auto: whichever backend _get_resolver() naturally selects
"""

from __future__ import annotations

import io
import logging
import tempfile
import wave
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from weave.type_wrappers.Content import (
    polyfile_magic_resolver,
    python_magic_resolver,
)
from weave.type_wrappers.Content.content import Content
from weave.type_wrappers.Content.utils import (
    _detect_from_resolver,
    get_extension_from_mimetype,
    get_mime_and_extension,
    guess_from_buffer,
    guess_from_extension,
    guess_from_filename,
)

# ---------------------------------------------------------------------------
# Resolver fixture: parametrizes every test to run with each backend
# ---------------------------------------------------------------------------

RESOLVER_IDS = ["python_magic", "polyfile", "auto"]


def _make_unavailable(module: Any) -> Any:
    """Return a patched is_available that always returns False."""
    return patch.object(module, "is_available", return_value=False)


def _get_utils_module():
    """Import the utils module avoiding the Content class re-export."""
    import importlib

    return importlib.import_module("weave.type_wrappers.Content.utils")


def _reset_resolver():
    mod = _get_utils_module()
    mod._resolver = mod._UNSET


@pytest.fixture(params=RESOLVER_IDS)
def resolver_backend(request):
    """Fixture that forces a specific resolver backend.

    Resets the cached resolver before each test so _get_resolver()
    re-evaluates availability.
    """
    backend = request.param
    _reset_resolver()

    if backend == "python_magic":
        with _make_unavailable(polyfile_magic_resolver):
            _reset_resolver()
            yield backend
    elif backend == "polyfile":
        with _make_unavailable(python_magic_resolver):
            _reset_resolver()
            yield backend
    else:
        yield backend

    _reset_resolver()


# ---------------------------------------------------------------------------
# Media byte fixtures (session-scoped, generated once)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def png_bytes() -> bytes:
    """Generate a valid PNG image as bytes."""
    img = Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8), "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def jpeg_bytes() -> bytes:
    """Generate a valid JPEG image as bytes."""
    img = Image.fromarray(np.full((4, 4, 3), 128, dtype=np.uint8), "RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(scope="session")
def wav_bytes() -> bytes:
    """Generate a valid WAV audio file as bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(22050)
        samples = (np.sin(np.linspace(0, np.pi, 2205)) * 32767).astype(np.int16)
        wf.writeframes(samples.tobytes())
    return buf.getvalue()


@pytest.fixture(scope="session")
def pdf_bytes() -> bytes:
    """Generate a valid PDF as bytes.

    Adds enough content to exceed typical magic detection thresholds (~2 KB),
    avoiding false-positive MIME matches on small binary payloads.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as pdf_canvas

    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=letter)
    for i in range(80):
        c.drawString(
            50, 750 - (i * 9), f"Line {i}: padding content for reliable MIME detection"
        )
    c.save()
    return buf.getvalue()


@pytest.fixture(scope="session")
def mp4_bytes() -> bytes:
    """Generate a minimal valid MP4 container as bytes."""
    ftyp = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2mp41"
    mdat = b"\x00\x00\x00\x08mdat"
    moov = b"\x00\x00\x00\x08moov"
    return ftyp + mdat + moov


@pytest.fixture(scope="session")
def gif_bytes() -> bytes:
    """Generate a valid GIF image as bytes."""
    img = Image.fromarray(np.zeros((4, 4, 3), dtype=np.uint8), "RGB")
    buf = io.BytesIO()
    img.save(buf, format="GIF")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Media file fixtures (session-scoped, written to tmp)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def png_file(tmp_path_factory, png_bytes) -> Path:
    p = tmp_path_factory.mktemp("media") / "test.png"
    p.write_bytes(png_bytes)
    return p


@pytest.fixture(scope="session")
def jpeg_file(tmp_path_factory, jpeg_bytes) -> Path:
    p = tmp_path_factory.mktemp("media") / "test.jpg"
    p.write_bytes(jpeg_bytes)
    return p


@pytest.fixture(scope="session")
def wav_file(tmp_path_factory, wav_bytes) -> Path:
    p = tmp_path_factory.mktemp("media") / "test.wav"
    p.write_bytes(wav_bytes)
    return p


@pytest.fixture(scope="session")
def pdf_file(tmp_path_factory, pdf_bytes) -> Path:
    p = tmp_path_factory.mktemp("media") / "test.pdf"
    p.write_bytes(pdf_bytes)
    return p


@pytest.fixture(scope="session")
def mp4_file(tmp_path_factory, mp4_bytes) -> Path:
    p = tmp_path_factory.mktemp("media") / "test.mp4"
    p.write_bytes(mp4_bytes)
    return p


@pytest.fixture(scope="session")
def extensionless_png_file(tmp_path_factory, png_bytes) -> Path:
    """A PNG file saved without any file extension."""
    p = tmp_path_factory.mktemp("media") / "noext_image"
    p.write_bytes(png_bytes)
    return p


# ---------------------------------------------------------------------------
# Test: resolver detection from buffer
# ---------------------------------------------------------------------------

BUFFER_CASES = [
    ("png_bytes", "image/png"),
    ("jpeg_bytes", "image/jpeg"),
    ("wav_bytes", "audio/x-wav"),
    ("pdf_bytes", "application/pdf"),
    ("gif_bytes", "image/gif"),
]


class TestResolverDetectFromBuffer:
    """Verify that each resolver correctly identifies MIME type from raw bytes."""

    @pytest.mark.parametrize(("fixture_name", "expected_mime"), BUFFER_CASES)
    def test_mime_from_buffer(
        self, fixture_name: str, expected_mime: str, resolver_backend, request
    ):
        buffer = request.getfixturevalue(fixture_name)
        mime, ext = _detect_from_resolver(filename=None, buffer=buffer)
        assert mime == expected_mime

    @pytest.mark.parametrize(("fixture_name", "expected_mime"), BUFFER_CASES)
    def test_extension_from_buffer_python_magic(
        self, fixture_name: str, expected_mime: str, resolver_backend, request
    ):
        """python-magic returns extensions; polyfile returns None."""
        buffer = request.getfixturevalue(fixture_name)
        _, ext = _detect_from_resolver(filename=None, buffer=buffer)

        if resolver_backend == "polyfile":
            assert ext is None, "polyfile should not return extension"
        else:
            # python_magic and auto (when python-magic is available)
            assert ext is not None, "python-magic should return an extension"
            assert ext.startswith(".")

    def test_empty_buffer(self, resolver_backend):
        """Empty buffer: polyfile returns None, python-magic returns application/x-empty."""
        mime, ext = _detect_from_resolver(filename=None, buffer=b"")
        if resolver_backend == "polyfile":
            assert mime is None
        else:
            # python-magic / auto may return "application/x-empty"
            assert mime is None or mime == "application/x-empty"

    def test_none_buffer_returns_none(self, resolver_backend):
        mime, ext = _detect_from_resolver(filename=None, buffer=None)
        assert mime is None
        assert ext is None


# ---------------------------------------------------------------------------
# Test: resolver detection from file
# ---------------------------------------------------------------------------

FILE_CASES = [
    ("png_file", "image/png", ".png"),
    ("jpeg_file", "image/jpeg", ".jpg"),
    ("wav_file", "audio/x-wav", ".wav"),
    ("pdf_file", "application/pdf", ".pdf"),
]


class TestResolverDetectFromFile:
    """Verify detection from an actual file path on disk."""

    @pytest.mark.parametrize(
        ("fixture_name", "expected_mime", "expected_ext"), FILE_CASES
    )
    def test_mime_from_file(
        self,
        fixture_name: str,
        expected_mime: str,
        expected_ext: str,
        resolver_backend,
        request,
    ):
        file_path = request.getfixturevalue(fixture_name)
        mime, ext = _detect_from_resolver(filename=str(file_path), buffer=None)

        if resolver_backend == "polyfile":
            # polyfile ignores filename, needs buffer
            assert mime is None
        else:
            assert mime == expected_mime

    @pytest.mark.parametrize(
        ("fixture_name", "expected_mime", "expected_ext"), FILE_CASES
    )
    def test_extension_from_file_python_magic(
        self,
        fixture_name: str,
        expected_mime: str,
        expected_ext: str,
        resolver_backend,
        request,
    ):
        """python-magic can detect extension from file; polyfile cannot."""
        file_path = request.getfixturevalue(fixture_name)
        _, ext = _detect_from_resolver(filename=str(file_path), buffer=None)

        if resolver_backend == "polyfile":
            assert ext is None
        else:
            assert ext is not None
            assert ext.startswith(".")

    def test_nonexistent_file_falls_back_to_buffer(self, resolver_backend, png_bytes):
        """When filename doesn't exist, should fall back to buffer detection."""
        mime, ext = _detect_from_resolver(
            filename="/nonexistent/file.png", buffer=png_bytes
        )
        assert mime == "image/png"

    def test_extensionless_file_detected_from_content(
        self, resolver_backend, extensionless_png_file, png_bytes
    ):
        """A file with no extension should still be identified by its content."""
        mime, ext = _detect_from_resolver(
            filename=str(extensionless_png_file),
            buffer=png_bytes,
        )
        assert mime == "image/png"


# ---------------------------------------------------------------------------
# Test: get_mime_and_extension (full pipeline)
# ---------------------------------------------------------------------------


class TestGetMimeAndExtension:
    """Test the full detection pipeline in utils.get_mime_and_extension."""

    def test_both_provided_returns_immediately(self, resolver_backend):
        mime, ext = get_mime_and_extension(
            mimetype="text/html",
            extension=".html",
            filename=None,
            buffer=None,
        )
        assert mime == "text/html"
        assert ext == ".html"

    def test_mimetype_only_resolves_extension(self, resolver_backend):
        mime, ext = get_mime_and_extension(
            mimetype="image/png",
            extension=None,
            filename=None,
            buffer=None,
        )
        assert mime == "image/png"
        assert ext == ".png"

    def test_extension_only_resolves_mimetype(self, resolver_backend):
        mime, ext = get_mime_and_extension(
            mimetype=None,
            extension=".pdf",
            filename=None,
            buffer=None,
        )
        assert mime == "application/pdf"
        assert ext == ".pdf"

    def test_filename_resolves_via_mimetypes(self, resolver_backend):
        """Filename-based detection (mimetypes) runs before content detection."""
        mime, ext = get_mime_and_extension(
            mimetype=None,
            extension=None,
            filename="report.pdf",
            buffer=None,
        )
        assert mime == "application/pdf"

    def test_buffer_detection_as_fallback(self, resolver_backend, png_bytes):
        """When filename and extension are absent, buffer detection kicks in."""
        mime, ext = get_mime_and_extension(
            mimetype=None,
            extension=None,
            filename=None,
            buffer=png_bytes,
        )
        assert mime == "image/png"

    def test_filename_takes_priority_over_buffer(self, resolver_backend, wav_bytes):
        """Mimetypes from filename should be tried before buffer detection."""
        mime, ext = get_mime_and_extension(
            mimetype=None,
            extension=None,
            filename="music.mp3",  # mimetypes says audio/mpeg
            buffer=wav_bytes,  # buffer says audio/x-wav
        )
        # Filename-based detection should win
        assert mime == "audio/mpeg"

    @pytest.mark.parametrize(
        ("buffer_fixture", "expected_mime"),
        [
            ("png_bytes", "image/png"),
            ("pdf_bytes", "application/pdf"),
            ("wav_bytes", "audio/x-wav"),
            ("jpeg_bytes", "image/jpeg"),
        ],
    )
    def test_buffer_only_detection(
        self,
        buffer_fixture: str,
        expected_mime: str,
        resolver_backend,
        request,
    ):
        buffer = request.getfixturevalue(buffer_fixture)
        mime, ext = get_mime_and_extension(
            mimetype=None,
            extension=None,
            filename=None,
            buffer=buffer,
        )
        assert mime == expected_mime

    def test_defaults_when_nothing_available(self, resolver_backend):
        mime, ext = get_mime_and_extension(
            mimetype=None,
            extension=None,
            filename=None,
            buffer=None,
        )
        assert mime == "application/octet-stream"
        assert ext == ""

    def test_custom_defaults(self, resolver_backend):
        mime, ext = get_mime_and_extension(
            mimetype=None,
            extension=None,
            filename=None,
            buffer=None,
            default_mimetype="text/plain",
            default_extension=".txt",
        )
        assert mime == "text/plain"
        assert ext == ".txt"

    def test_extension_normalized_with_dot(self, resolver_backend):
        """Extensions without a dot prefix should be normalized."""
        mime, ext = get_mime_and_extension(
            mimetype="image/png",
            extension="png",
            filename=None,
            buffer=None,
        )
        assert ext == ".png"

    def test_empty_buffer_treated_as_none(self, resolver_backend):
        mime, ext = get_mime_and_extension(
            mimetype=None,
            extension=".txt",
            filename=None,
            buffer=b"",
        )
        assert mime == "text/plain"
        assert ext == ".txt"


# ---------------------------------------------------------------------------
# Test: guess_from_buffer (public API)
# ---------------------------------------------------------------------------


class TestGuessFromBuffer:
    @pytest.mark.parametrize(("fixture_name", "expected_mime"), BUFFER_CASES)
    def test_returns_correct_mime(
        self,
        fixture_name: str,
        expected_mime: str,
        resolver_backend,
        request,
    ):
        buffer = request.getfixturevalue(fixture_name)
        mime = guess_from_buffer(buffer)
        assert mime == expected_mime

    def test_empty_buffer_returns_none(self, resolver_backend):
        assert guess_from_buffer(b"") is None


# ---------------------------------------------------------------------------
# Test: guess_from_filename and guess_from_extension (stdlib mimetypes)
# ---------------------------------------------------------------------------


class TestMimetypesHelpers:
    """These don't depend on the resolver but are exercised for completeness."""

    @pytest.mark.parametrize(
        ("filename", "expected_mime"),
        [
            ("image.png", "image/png"),
            ("doc.pdf", "application/pdf"),
            ("song.mp3", "audio/mpeg"),
            ("page.html", "text/html"),
            ("data.json", "application/json"),
            ("readme.md", "text/markdown"),
            ("style.css", "text/css"),
        ],
    )
    def test_guess_from_filename(self, filename, expected_mime):
        assert guess_from_filename(filename) == expected_mime

    @pytest.mark.parametrize(
        ("ext", "expected_mime"),
        [
            (".png", "image/png"),
            ("png", "image/png"),
            (".pdf", "application/pdf"),
            ("mp3", "audio/mpeg"),
        ],
    )
    def test_guess_from_extension(self, ext, expected_mime):
        assert guess_from_extension(ext) == expected_mime

    @pytest.mark.parametrize(
        ("mime", "expected_ext"),
        [
            ("image/png", ".png"),
            ("application/pdf", ".pdf"),
            ("text/html", ".html"),
        ],
    )
    def test_get_extension_from_mimetype(self, mime, expected_ext):
        assert get_extension_from_mimetype(mime) == expected_ext


# ---------------------------------------------------------------------------
# Test: Content class integration with each resolver
# ---------------------------------------------------------------------------


class TestContentIntegration:
    """End-to-end tests creating Content objects under each resolver backend."""

    def test_from_path_png(self, resolver_backend, png_file):
        c = Content.from_path(png_file)
        assert c.mimetype == "image/png"
        assert c.extension == ".png"
        assert c.size > 0

    def test_from_path_pdf(self, resolver_backend, pdf_file):
        c = Content.from_path(pdf_file)
        assert c.mimetype == "application/pdf"
        assert c.extension == ".pdf"

    def test_from_path_wav(self, resolver_backend, wav_file):
        c = Content.from_path(wav_file)
        assert c.mimetype in ("audio/x-wav", "audio/wav")
        assert c.extension == ".wav"

    def test_from_bytes_with_extension(self, resolver_backend, png_bytes):
        c = Content.from_bytes(png_bytes, extension="png")
        assert c.mimetype == "image/png"
        assert c.extension == ".png"

    def test_from_bytes_without_hint(self, resolver_backend, pdf_bytes):
        """With no extension or mimetype hint, must detect from buffer."""
        c = Content.from_bytes(pdf_bytes)
        assert c.mimetype == "application/pdf"

    def test_from_bytes_mimetype_only(self, resolver_backend, wav_bytes):
        c = Content.from_bytes(wav_bytes, mimetype="audio/x-wav")
        assert c.mimetype == "audio/x-wav"
        assert c.extension is not None  # should be resolved from mimetype

    def test_from_text(self, resolver_backend):
        c = Content.from_text("hello world", extension="txt")
        assert c.mimetype == "text/plain"
        assert c.extension == ".txt"

    def test_from_path_extensionless(self, resolver_backend, extensionless_png_file):
        """File with no extension should still detect MIME from content."""
        c = Content.from_path(extensionless_png_file)
        assert c.mimetype == "image/png"

    def test_from_bytes_empty(self, resolver_backend):
        c = Content.from_bytes(b"", extension="bin")
        assert c.size == 0
        assert c.extension == ".bin"

    def test_roundtrip_save_load(self, resolver_backend, png_bytes):
        """Save content to disk and re-read it via from_path."""
        c = Content.from_bytes(png_bytes, extension="png")
        with tempfile.TemporaryDirectory() as tmpdir:
            dest = Path(tmpdir) / "roundtrip.png"
            c.save(dest)
            c2 = Content.from_path(dest)
            assert c2.data == c.data
            assert c2.mimetype == c.mimetype
            assert c2.extension == c.extension


# ---------------------------------------------------------------------------
# Test: no resolver available (graceful degradation)
# ---------------------------------------------------------------------------


class TestNoResolverAvailable:
    """Verify behaviour when neither python-magic nor polyfile is installed."""

    @pytest.fixture(autouse=True)
    def _disable_all_resolvers(self):
        _reset_resolver()
        with (
            _make_unavailable(python_magic_resolver),
            _make_unavailable(polyfile_magic_resolver),
        ):
            _reset_resolver()
            yield
        _reset_resolver()

    def test_guess_from_buffer_warns(self, caplog):
        with caplog.at_level(
            logging.WARNING, logger="weave.type_wrappers.Content.utils"
        ):
            result = guess_from_buffer(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        assert result is None
        assert "python-magic or polyfile" in caplog.text

    def test_get_mime_and_extension_uses_defaults(self):
        mime, ext = get_mime_and_extension(
            mimetype=None,
            extension=None,
            filename=None,
            buffer=b"\x89PNG\r\n",
        )
        assert mime == "application/octet-stream"
        assert ext == ""

    def test_mimetypes_still_works_without_resolver(self):
        """Stdlib mimetypes detection should work even without a resolver."""
        mime, ext = get_mime_and_extension(
            mimetype=None,
            extension=None,
            filename="image.png",
            buffer=None,
        )
        assert mime == "image/png"

    def test_content_from_bytes_with_extension_still_works(self):
        """When extension is provided, no resolver needed."""
        c = Content.from_bytes(b"data", extension="txt")
        assert c.mimetype == "text/plain"
        assert c.extension == ".txt"

    def test_detect_from_resolver_returns_none(self):
        mime, ext = _detect_from_resolver(filename=None, buffer=b"test")
        assert mime is None
        assert ext is None


# ---------------------------------------------------------------------------
# Test: python-magic specific from_file behaviour
# ---------------------------------------------------------------------------


class TestPythonMagicFromFile:
    """Tests specific to python-magic's from_file capability."""

    @pytest.fixture(autouse=True)
    def _force_python_magic(self):
        _reset_resolver()
        with _make_unavailable(polyfile_magic_resolver):
            _reset_resolver()
            yield
        _reset_resolver()

    def test_from_file_detects_mime_and_extension(self, png_file):
        mime, ext = python_magic_resolver.detect(filename=str(png_file), buffer=None)
        assert mime == "image/png"
        assert ext is not None
        assert ext.startswith(".")

    def test_from_file_nonexistent_falls_back_to_buffer(self, png_bytes):
        mime, ext = python_magic_resolver.detect(
            filename="/does/not/exist.png", buffer=png_bytes
        )
        assert mime == "image/png"

    def test_from_file_nonexistent_no_buffer_returns_none(self):
        mime, ext = python_magic_resolver.detect(
            filename="/does/not/exist.png", buffer=None
        )
        assert mime is None
        assert ext is None

    def test_extensionless_file_detected(self, extensionless_png_file):
        """python-magic detects MIME from file content, ignoring extension."""
        mime, ext = python_magic_resolver.detect(
            filename=str(extensionless_png_file), buffer=None
        )
        assert mime == "image/png"


# ---------------------------------------------------------------------------
# Test: polyfile specific behaviour
# ---------------------------------------------------------------------------


class TestPolyfileResolver:
    """Tests specific to polyfile's buffer-only detection."""

    @pytest.fixture(autouse=True)
    def _force_polyfile(self):
        _reset_resolver()
        with _make_unavailable(python_magic_resolver):
            _reset_resolver()
            yield
        _reset_resolver()

    def test_detect_ignores_filename(self, png_bytes):
        """Polyfile should return the same result regardless of filename."""
        mime_with, _ = polyfile_magic_resolver.detect(
            filename="image.png", buffer=png_bytes
        )
        mime_without, _ = polyfile_magic_resolver.detect(
            filename=None, buffer=png_bytes
        )
        assert mime_with == mime_without == "image/png"

    def test_detect_never_returns_extension(self, pdf_bytes):
        _, ext = polyfile_magic_resolver.detect(filename=None, buffer=pdf_bytes)
        assert ext is None

    def test_detect_no_buffer_returns_none(self):
        mime, ext = polyfile_magic_resolver.detect(filename="report.pdf", buffer=None)
        assert mime is None
        assert ext is None

    def test_detect_empty_buffer_returns_none(self):
        mime, ext = polyfile_magic_resolver.detect(filename=None, buffer=b"")
        assert mime is None
        assert ext is None
