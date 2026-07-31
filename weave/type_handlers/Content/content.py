"""Defines the custom File weave type."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from weave.type_wrappers.Content.content import Content


from weave.trace.serialization.custom_objs import MemTraceFilesArtifact


def save(obj: Content, artifact: MemTraceFilesArtifact, name: str) -> None:
    with artifact.new_file("content", binary=True) as f:
        f.write(obj.data)

    with artifact.new_file("metadata.json", binary=False) as f:
        metadata = obj.model_dump(exclude={"data"})
        json.dump(metadata, f)


def load(artifact: MemTraceFilesArtifact, name: str, val: Any) -> Content:
    from weave.type_wrappers.Content.content import Content
    from weave.type_wrappers.Content.content_types import (
        ResolvedContentArgs,
        ResolvedContentArgsWithoutData,
    )

    metadata_path = artifact.path("metadata.json")

    with open(metadata_path) as f:
        metadata: ResolvedContentArgsWithoutData = json.load(f)

    with open(artifact.path("content"), "rb") as f:
        data = f.read()

    resolved_args: ResolvedContentArgs = {"data": data, **metadata}

    return Content._from_resolved_args(resolved_args)


def register() -> None:
    from weave.trace.serialization import serializer
    from weave.type_wrappers.Content.content import Content

    serializer.register_serializer(Content, save, load)
