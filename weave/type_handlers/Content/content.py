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

    path = artifact.path("content")
    return Content(path, metadata["mimetype"])


def instance_check(obj: object) -> bool:
    if isinstance(obj, Content):
        return True

    ser_id = obj.__module__ + "." + getattr(obj, "__name__", "")
    print(ser_id)
    return ser_id.startswith("weave.") and ser_id.endswith(".Content")


def register() -> None:
    serializer.register_serializer(Content, save, load, instance_check)
