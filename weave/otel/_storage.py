"""Internal storage utilities for weave.otel media capture.

Uploads content bytes to the Weave file store (content-addressed) and
resolves the project_id from OTel span resource attributes or the global
WeaveClient.
"""

from __future__ import annotations

import base64
import io
import logging
import os
from pathlib import Path
from typing import Any

import requests

from weave.shared.digest import bytes_digest

logger = logging.getLogger(__name__)

_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"RIFF", "audio/wav"),
    (b"\xff\xfb", "audio/mpeg"),
    (b"\xff\xf3", "audio/mpeg"),
    (b"\xff\xf2", "audio/mpeg"),
    (b"ID3", "audio/mpeg"),
    (b"\x1aE\xdf\xa3", "video/webm"),
    (b"\x00\x00\x00\x1cftyp", "video/mp4"),
    (b"\x00\x00\x00\x18ftyp", "video/mp4"),
    (b"\x00\x00\x00\x20ftyp", "video/mp4"),
    (b"OggS", "audio/ogg"),
    (b"fLaC", "audio/flac"),
    (b"WEBP", "image/webp"),
]

_EXT_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".pdf": "application/pdf",
}


def detect_media_type(data: bytes, filename: str | None = None) -> str:
    """Auto-detect MIME type from bytes magic numbers or file extension."""
    for magic, mime in _MAGIC_SIGNATURES:
        if data[: len(magic)] == magic:
            return mime
    if data[4:8] == b"WEBP":
        return "image/webp"
    if filename:
        ext = Path(filename).suffix.lower()
        if ext in _EXT_TO_MIME:
            return _EXT_TO_MIME[ext]
    return "application/octet-stream"


def resolve_content_bytes(data: Any) -> tuple[bytes, str | None]:
    """Normalize various input types to raw bytes.

    Returns:
        Tuple of (bytes, optional_filename).
    """
    if isinstance(data, bytes):
        return data, None
    if isinstance(data, (str, Path)):
        p = Path(data)
        if p.is_file():
            return p.read_bytes(), p.name
        return str(data).encode("utf-8"), None
    if isinstance(data, io.IOBase):
        name = getattr(data, "name", None)
        return data.read(), name
    try:
        import PIL.Image

        if isinstance(data, PIL.Image.Image):
            buf = io.BytesIO()
            fmt = data.format or "PNG"
            data.save(buf, format=fmt)
            ext = fmt.lower()
            return buf.getvalue(), f"image.{ext}"
    except ImportError:
        pass
    raise TypeError(f"Cannot convert {type(data).__name__} to bytes")


def resolve_project_id() -> str | None:
    """Resolve project_id from the active OTel span or WeaveClient."""
    try:
        from opentelemetry import trace as otel_trace

        span = otel_trace.get_current_span()
        if span and span.is_recording():
            resource = getattr(span, "resource", None)
            if resource:
                attrs = resource.attributes
                entity = attrs.get("wandb.entity")
                project = attrs.get("wandb.project")
                if entity and project:
                    return f"{entity}/{project}"
    except ImportError:
        pass

    try:
        from weave.trace.context.weave_client_context import get_weave_client

        client = get_weave_client()
        if client:
            return f"{client.project_id}"
    except (ImportError, Exception):
        pass

    return None


def resolve_trace_server_url() -> str | None:
    """Resolve the trace server URL for file uploads."""
    url = os.environ.get("WF_TRACE_SERVER_URL")
    if url:
        return url

    try:
        from weave.trace.context.weave_client_context import get_weave_client

        client = get_weave_client()
        if (
            client
            and hasattr(client, "server")
            and hasattr(client.server, "_server_url")
        ):
            return client.server._server_url
    except (ImportError, Exception):
        pass

    return None


def resolve_api_key() -> str | None:
    """Resolve the W&B API key for authentication."""
    key = os.environ.get("WANDB_API_KEY")
    if key:
        return key

    try:
        from weave.trace.context.weave_client_context import get_weave_client

        client = get_weave_client()
        if client and hasattr(client, "server"):
            server = client.server
            if hasattr(server, "_api_key"):
                return server._api_key
    except (ImportError, Exception):
        pass

    return None


def upload_content(content: bytes, project_id: str) -> str:
    """Upload content bytes to the Weave file store.

    Args:
        content: Raw bytes to store.
        project_id: The project to store under.

    Returns:
        The content-addressed digest string.
    """
    digest = bytes_digest(content)

    server_url = resolve_trace_server_url()
    api_key = resolve_api_key()

    if not server_url:
        logger.debug("No trace server URL available, skipping upload")
        return digest

    url = f"{server_url}/file/create"
    headers: dict[str, str] = {}
    if api_key:
        creds = base64.b64encode(f"api:{api_key}".encode()).decode()
        headers["Authorization"] = f"Basic {creds}"

    try:
        resp = requests.post(
            url,
            files={
                "file": ("content", io.BytesIO(content), "application/octet-stream")
            },
            data={"project_id": project_id},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
    except Exception:
        logger.debug("Failed to upload content to %s", url, exc_info=True)

    return digest
