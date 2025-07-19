"""Defines the custom File weave type."""

from __future__ import annotations

import json
import logging

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact
from weave.type_wrappers import Content

logger = logging.getLogger(__name__)


def save(obj: Content, artifact: MemTraceFilesArtifact, name: str) -> None:
    with artifact.new_file("content", binary=True) as f:
        f.write(obj.data)

    with artifact.new_file("metadata.json", binary=False) as f:
        json.dump(obj.metadata, f)


def load(artifact: MemTraceFilesArtifact, name: str) -> Content:
    metadata_path = artifact.path("metadata.json")
    with open(metadata_path) as f:
        metadata = json.load(f)

    with open(artifact.path("content"), "rb") as f:
        data = f.read()
    return Content(data, **metadata)


def register() -> None:
    serializer.register_serializer(Content, save, load)
