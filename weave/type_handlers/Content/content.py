"""Defines the custom File weave type."""

from __future__ import annotations

import json

from weave.trace.serialization import serializer
from weave.trace.serialization.custom_objs import MemTraceFilesArtifact
from weave.type_wrappers import Content
from weave.type_wrappers.Content.content import (
    ResolvedContentArgs,
    ResolvedContentArgsWithoutData,
)


def save(obj: Content, artifact: MemTraceFilesArtifact, name: str) -> None:
    with artifact.new_file("content", binary=True) as f:
        f.write(obj.data)

    with artifact.new_file("metadata.json", binary=False) as f:
        # The serialization layer sets non-private fields on pydantic models and saved files
        # Which we do not want to include here.
        # By doing this, we can ensure that those fields can be set but will never show
        metadata = obj.model_dump(exclude={"data", "ref"})
        json.dump(metadata, f)


def load(artifact: MemTraceFilesArtifact, name: str) -> Content:
    metadata_path = artifact.path("metadata.json")
    with open(metadata_path) as f:
        metadata: ResolvedContentArgsWithoutData = json.load(f)

    with open(artifact.path("content"), "rb") as f:
        data = f.read()

    resolved_args: ResolvedContentArgs = {"data": data, **metadata}

    return Content._from_resolved_args(resolved_args)


def register() -> None:
    serializer.register_serializer(Content, save, load)
