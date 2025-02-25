"""Defines the custom DateTime weave type."""

from __future__ import annotations

import datetime
import json

from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact


class DatetimeWithArtifact(datetime.datetime):
    """A datetime class that can hold an artifact reference.

    This wrapper class is necessary because Python's datetime.datetime is immutable
    and doesn't allow adding new attributes. Weave's serialization system requires
    all custom objects to store an 'art' attribute referencing their artifact.

    While some types like PIL.Image allow adding attributes dynamically, datetime
    objects raise AttributeError if you try to add new attributes. This wrapper
    provides the same datetime functionality but adds the ability to store the
    required artifact reference.
    """

    art: MemTraceFilesArtifact | None = None


def save(obj: datetime.datetime, artifact: MemTraceFilesArtifact, name: str) -> None:
    """Serialize a datetime object to ISO format with timezone information.

    If the datetime object is naive (has no timezone), it will be assumed to be UTC.
    """
    if obj.tzinfo is None:
        obj = obj.replace(tzinfo=datetime.timezone.utc)

    # This is stored as JSON to match the pattern used by other handlers, but it
    # can otherwise be stored as a string or not use artifact at all
    with artifact.new_file(f"{name}.json") as f:
        json_str = json.dumps({"isoformat": obj.isoformat()})
        f.write(json_str)


def load(artifact: MemTraceFilesArtifact, name: str) -> DatetimeWithArtifact:
    """Deserialize an ISO format string back to a datetime object with timezone.

    Returns a DatetimeWithArtifact instead of a regular datetime because standard
    datetime objects cannot store the artifact reference that Weave requires.
    The returned object behaves exactly like a regular datetime but can also
    store the required artifact reference.
    """
    try:
        # Try to open as a string first
        with artifact.open(f"{name}.json") as f:
            data = json.load(f)
    except AttributeError:
        # If that fails, try to handle the case where the value is a string
        val = artifact.path_contents.get(f"{name}.json")
        if isinstance(val, str):
            data = json.loads(val)
        else:
            raise

    result = DatetimeWithArtifact.fromisoformat(data["isoformat"])
    result.art = artifact
    return result


def inline_serialize(obj: datetime.datetime) -> dict:
    """Serialize a datetime object to a dictionary without using artifacts.

    This provides a more efficient serialization option that avoids the network
    overhead of reading from artifacts.

    If the datetime object is naive (has no timezone), it will be assumed to be UTC.
    """
    if obj.tzinfo is None:
        obj = obj.replace(tzinfo=datetime.timezone.utc)

    return {"isoformat": obj.isoformat()}


def inline_deserialize(data: dict) -> DatetimeWithArtifact:
    """Deserialize a dictionary back to a datetime object with timezone.

    Returns a DatetimeWithArtifact to maintain compatibility with the rest of
    the system, but no artifact reference is needed since the data was serialized
    inline.
    """
    result = DatetimeWithArtifact.fromisoformat(data["isoformat"])
    result.art = None
    return result


def register() -> None:
    serializer.register_serializer(
        datetime.datetime,
        save,
        load,
        inline_serialize=inline_serialize,
        inline_deserialize=inline_deserialize,
    )
