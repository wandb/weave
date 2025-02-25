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

    All datetime objects are converted to UTC for consistent serialization.
    """
    # If the datetime is naive, convert it to UTC
    if obj.tzinfo is None:
        obj = obj.replace(tzinfo=datetime.timezone.utc)
    else:
        # Convert to UTC if it has a timezone
        obj = obj.astimezone(datetime.timezone.utc)

    # Store the datetime with its timezone
    with artifact.new_file(f"{name}.json") as f:
        json_str = json.dumps({"isoformat": obj.isoformat()})
        f.write(json_str)


def load(artifact: MemTraceFilesArtifact, name: str) -> datetime.datetime:
    """Deserialize an ISO format string back to a datetime object with UTC timezone.

    All datetime objects are returned with UTC timezone for consistency.
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

    # Create a datetime and ensure it's in UTC
    dt = datetime.datetime.fromisoformat(data["isoformat"])
    # If the datetime is naive, assume UTC
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    # Otherwise, convert to UTC
    return dt.astimezone(datetime.timezone.utc)


def inline_serialize(obj: datetime.datetime) -> dict:
    """Serialize a datetime object to a dictionary without using artifacts.

    All datetime objects are converted to UTC for consistent serialization.
    """
    # If the datetime is naive, convert it to UTC
    if obj.tzinfo is None:
        obj = obj.replace(tzinfo=datetime.timezone.utc)
    else:
        # Convert to UTC if it has a timezone
        obj = obj.astimezone(datetime.timezone.utc)

    # Store the datetime with its timezone
    return {"isoformat": obj.isoformat()}


def inline_deserialize(data: dict) -> datetime.datetime:
    """Deserialize a dictionary back to a datetime object with UTC timezone.

    All datetime objects are returned with UTC timezone for consistency.
    """
    # Create a datetime and ensure it's in UTC
    dt = datetime.datetime.fromisoformat(data["isoformat"])
    # If the datetime is naive, assume UTC
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    # Otherwise, convert to UTC
    return dt.astimezone(datetime.timezone.utc)


def register() -> None:
    serializer.register_serializer(
        datetime.datetime,
        save,
        load,
        inline_serialize=inline_serialize,
        inline_deserialize=inline_deserialize,
    )
