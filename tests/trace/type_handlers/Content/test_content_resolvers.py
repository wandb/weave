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

import importlib
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
# Resolver detection from buffer
# ---------------------------------------------------------------------------

BUFFER_CASES = [
    ("png_bytes", "image/png"),
    ("jpeg_bytes", "image/jpeg"),
    # libmagic detects audio/x-wav; normalized to canonical audio/wav.
    ("wav_bytes", "audio/wav"),
    ("pdf_bytes", "application/pdf"),
    ("gif_bytes", "image/gif"),
]


@pytest.mark.parametrize(("fixture_name", "expected_mime"), BUFFER_CASES)
def test_detect_from_buffer(fixture_name, expected_mime, resolver_backend, request):
    """MIME from raw bytes, plus extension-presence contract per backend."""
    buffer = request.getfixturevalue(fixture_name)
    mime, ext = _detect_from_resolver(filename=None, buffer=buffer)
    assert mime == expected_mime
    if resolver_backend == "polyfile":
        assert ext is None, "polyfile should not return extension"
    else:
        assert ext is not None, "python-magic should return an extension"
        assert ext.startswith(".")


def test_detect_from_buffer_edge_cases(resolver_backend):
    """Empty and None buffers across backends."""
    mime, ext = _detect_from_resolver(filename=None, buffer=b"")
    if resolver_backend == "polyfile":
        assert mime is None
    else:
        assert mime is None or mime == "application/x-empty"

    mime, ext = _detect_from_resolver(filename=None, buffer=None)
    assert mime is None
    assert ext is None


# ---------------------------------------------------------------------------
# Resolver detection from file
# ---------------------------------------------------------------------------

FILE_CASES = [
    ("png_file", "image/png", ".png"),
    ("jpeg_file", "image/jpeg", ".jpg"),
    # libmagic detects audio/x-wav; normalized to canonical audio/wav.
    ("wav_file", "audio/wav", ".wav"),
    ("pdf_file", "application/pdf", ".pdf"),
]


@pytest.mark.parametrize(("fixture_name", "expected_mime", "expected_ext"), FILE_CASES)
def test_detect_from_file(
    fixture_name, expected_mime, expected_ext, resolver_backend, request
):
    """MIME + extension contract from a real file path; polyfile ignores filename."""
    file_path = request.getfixturevalue(fixture_name)
    mime, ext = _detect_from_resolver(filename=str(file_path), buffer=None)
    if resolver_backend == "polyfile":
        assert mime is None
        assert ext is None
    else:
        assert mime == expected_mime
        assert ext is not None
        assert ext.startswith(".")


def test_detect_from_file_fallbacks(
    resolver_backend, extensionless_png_file, png_bytes
):
    """Nonexistent path falls back to buffer; extensionless file detected by content."""
    mime, _ = _detect_from_resolver(filename="/nonexistent/file.png", buffer=png_bytes)
    assert mime == "image/png"

    mime, _ = _detect_from_resolver(
        filename=str(extensionless_png_file), buffer=png_bytes
    )
    assert mime == "image/png"


# ---------------------------------------------------------------------------
# get_mime_and_extension (full pipeline)
# ---------------------------------------------------------------------------


def test_get_mime_and_extension_priority(resolver_backend, png_bytes, wav_bytes):
    """Resolution priority: explicit args > filename mimetypes > buffer detection."""
    # both provided returns immediately
    assert get_mime_and_extension(
        mimetype="text/html", extension=".html", filename=None, buffer=None
    ) == ("text/html", ".html")
    # mimetype only resolves extension
    assert get_mime_and_extension(
        mimetype="image/png", extension=None, filename=None, buffer=None
    ) == ("image/png", ".png")
    # extension only resolves mimetype
    assert get_mime_and_extension(
        mimetype=None, extension=".pdf", filename=None, buffer=None
    ) == ("application/pdf", ".pdf")
    # filename resolves via mimetypes (before content detection)
    mime, _ = get_mime_and_extension(
        mimetype=None, extension=None, filename="report.pdf", buffer=None
    )
    assert mime == "application/pdf"
    # buffer detection as fallback
    mime, _ = get_mime_and_extension(
        mimetype=None, extension=None, filename=None, buffer=png_bytes
    )
    assert mime == "image/png"
    # filename takes priority over buffer (mimetypes audio/mpeg beats audio/wav)
    mime, _ = get_mime_and_extension(
        mimetype=None, extension=None, filename="music.mp3", buffer=wav_bytes
    )
    assert mime == "audio/mpeg"


@pytest.mark.parametrize(
    ("buffer_fixture", "expected_mime"),
    [
        ("png_bytes", "image/png"),
        ("pdf_bytes", "application/pdf"),
        ("wav_bytes", "audio/wav"),
        ("jpeg_bytes", "image/jpeg"),
    ],
)
def test_get_mime_and_extension_buffer_only(
    buffer_fixture, expected_mime, resolver_backend, request
):
    buffer = request.getfixturevalue(buffer_fixture)
    mime, _ = get_mime_and_extension(
        mimetype=None, extension=None, filename=None, buffer=buffer
    )
    assert mime == expected_mime


def test_get_mime_and_extension_defaults_and_normalization(resolver_backend):
    """Default fallbacks, custom defaults, dot-normalization, empty-buffer handling."""
    assert get_mime_and_extension(
        mimetype=None, extension=None, filename=None, buffer=None
    ) == ("application/octet-stream", "")
    assert get_mime_and_extension(
        mimetype=None,
        extension=None,
        filename=None,
        buffer=None,
        default_mimetype="text/plain",
        default_extension=".txt",
    ) == ("text/plain", ".txt")
    # extension without dot prefix is normalized
    _, ext = get_mime_and_extension(
        mimetype="image/png", extension="png", filename=None, buffer=None
    )
    assert ext == ".png"
    # empty buffer treated as none -> falls to provided extension
    assert get_mime_and_extension(
        mimetype=None, extension=".txt", filename=None, buffer=b""
    ) == ("text/plain", ".txt")


# ---------------------------------------------------------------------------
# Public mimetypes helpers (resolver-independent)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("fixture_name", "expected_mime"), BUFFER_CASES)
def test_guess_from_buffer(fixture_name, expected_mime, resolver_backend, request):
    buffer = request.getfixturevalue(fixture_name)
    assert guess_from_buffer(buffer) == expected_mime


def test_guess_from_buffer_empty(resolver_backend):
    assert guess_from_buffer(b"") is None


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
def test_guess_from_filename(filename, expected_mime):
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
def test_guess_from_extension(ext, expected_mime):
    assert guess_from_extension(ext) == expected_mime


@pytest.mark.parametrize(
    ("mime", "expected_ext"),
    [
        ("image/png", ".png"),
        ("application/pdf", ".pdf"),
        ("text/html", ".html"),
    ],
)
def test_get_extension_from_mimetype(mime, expected_ext):
    assert get_extension_from_mimetype(mime) == expected_ext


# ---------------------------------------------------------------------------
# Content class integration with each resolver
# ---------------------------------------------------------------------------


def test_content_from_path(resolver_backend, png_file, pdf_file, wav_file):
    """from_path detects mime + extension + size for png/pdf/wav."""
    c = Content.from_path(png_file)
    assert c.mimetype == "image/png"
    assert c.extension == ".png"
    assert c.size > 0

    c = Content.from_path(pdf_file)
    assert c.mimetype == "application/pdf"
    assert c.extension == ".pdf"

    c = Content.from_path(wav_file)
    # Detected audio/x-wav is normalized to canonical audio/wav.
    assert c.mimetype == "audio/wav"
    assert c.extension == ".wav"


def test_content_from_path_extensionless(resolver_backend, extensionless_png_file):
    """File with no extension still detects MIME from content."""
    c = Content.from_path(extensionless_png_file)
    assert c.mimetype == "image/png"


def test_content_from_bytes(resolver_backend, png_bytes, pdf_bytes, wav_bytes):
    """from_bytes with explicit extension, no hint, and explicit mimetype."""
    c = Content.from_bytes(png_bytes, extension="png")
    assert c.mimetype == "image/png"
    assert c.extension == ".png"

    # no extension or mimetype hint -> detect from buffer
    c = Content.from_bytes(pdf_bytes)
    assert c.mimetype == "application/pdf"

    # explicit caller mimetype is preserved; only detected types are normalized
    c = Content.from_bytes(wav_bytes, mimetype="audio/x-wav")
    assert c.mimetype == "audio/x-wav"
    assert c.extension is not None


def test_content_from_text_and_empty(resolver_backend):
    """from_text resolves text/plain; empty from_bytes keeps size 0 + extension."""
    c = Content.from_text("hello world", extension="txt")
    assert c.mimetype == "text/plain"
    assert c.extension == ".txt"

    c = Content.from_bytes(b"", extension="bin")
    assert c.size == 0
    assert c.extension == ".bin"


def test_content_roundtrip_save_load(resolver_backend, png_bytes):
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
# No resolver available (graceful degradation)
# ---------------------------------------------------------------------------


@pytest.fixture
def _no_resolvers():
    _reset_resolver()
    with (
        _make_unavailable(python_magic_resolver),
        _make_unavailable(polyfile_magic_resolver),
    ):
        _reset_resolver()
        yield
    _reset_resolver()


@pytest.mark.usefixtures("_no_resolvers")
def test_no_resolver_buffer_paths(caplog):
    """Without a resolver: buffer detect warns + returns None, defaults applied."""
    with caplog.at_level(logging.WARNING, logger="weave.type_wrappers.Content.utils"):
        result = guess_from_buffer(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    assert result is None
    assert "python-magic or polyfile" in caplog.text

    mime, ext = _detect_from_resolver(filename=None, buffer=b"test")
    assert mime is None
    assert ext is None

    assert get_mime_and_extension(
        mimetype=None, extension=None, filename=None, buffer=b"\x89PNG\r\n"
    ) == ("application/octet-stream", "")


@pytest.mark.usefixtures("_no_resolvers")
def test_no_resolver_mimetypes_still_work():
    """Stdlib mimetypes + explicit-extension paths work without any resolver."""
    mime, _ = get_mime_and_extension(
        mimetype=None, extension=None, filename="image.png", buffer=None
    )
    assert mime == "image/png"

    c = Content.from_bytes(b"data", extension="txt")
    assert c.mimetype == "text/plain"
    assert c.extension == ".txt"


# ---------------------------------------------------------------------------
# python-magic specific from_file behaviour
# ---------------------------------------------------------------------------


@pytest.fixture
def _force_python_magic():
    _reset_resolver()
    with _make_unavailable(polyfile_magic_resolver):
        _reset_resolver()
        yield
    _reset_resolver()


@pytest.mark.usefixtures("_force_python_magic")
def test_python_magic_from_file(png_file, extensionless_png_file, png_bytes):
    """python-magic detects from file (incl. extensionless) and via buffer fallback."""
    mime, ext = python_magic_resolver.detect(filename=str(png_file), buffer=None)
    assert mime == "image/png"
    assert ext is not None
    assert ext.startswith(".")

    mime, _ = python_magic_resolver.detect(
        filename=str(extensionless_png_file), buffer=None
    )
    assert mime == "image/png"

    mime, _ = python_magic_resolver.detect(
        filename="/does/not/exist.png", buffer=png_bytes
    )
    assert mime == "image/png"


@pytest.mark.usefixtures("_force_python_magic")
def test_python_magic_from_file_no_buffer_none():
    mime, ext = python_magic_resolver.detect(
        filename="/does/not/exist.png", buffer=None
    )
    assert mime is None
    assert ext is None


# ---------------------------------------------------------------------------
# polyfile specific behaviour
# ---------------------------------------------------------------------------


@pytest.fixture
def _force_polyfile():
    _reset_resolver()
    with _make_unavailable(python_magic_resolver):
        _reset_resolver()
        yield
    _reset_resolver()


@pytest.mark.usefixtures("_force_polyfile")
def test_polyfile_buffer_only(png_bytes, pdf_bytes):
    """Polyfile ignores filename, is buffer-only, never returns an extension."""
    mime_with, _ = polyfile_magic_resolver.detect(
        filename="image.png", buffer=png_bytes
    )
    mime_without, _ = polyfile_magic_resolver.detect(filename=None, buffer=png_bytes)
    assert mime_with == mime_without == "image/png"

    _, ext = polyfile_magic_resolver.detect(filename=None, buffer=pdf_bytes)
    assert ext is None


@pytest.mark.usefixtures("_force_polyfile")
def test_polyfile_no_buffer_none():
    """No buffer (with or without filename) and empty buffer both return None."""
    mime, ext = polyfile_magic_resolver.detect(filename="report.pdf", buffer=None)
    assert mime is None
    assert ext is None

    mime, ext = polyfile_magic_resolver.detect(filename=None, buffer=b"")
    assert mime is None
    assert ext is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unavailable(module: Any) -> Any:
    """Return a patched is_available that always returns False."""
    return patch.object(module, "is_available", return_value=False)


def _get_utils_module():
    """Import the utils module avoiding the Content class re-export."""
    return importlib.import_module("weave.type_wrappers.Content.utils")


def _reset_resolver() -> None:
    mod = _get_utils_module()
    mod._resolver = mod._UNSET
