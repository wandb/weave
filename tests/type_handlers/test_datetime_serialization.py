"""Tests for datetime serialization."""

from __future__ import annotations

import datetime

from weave.trace import custom_objs, serializer
from weave.trace.custom_objs import MemTraceFilesArtifact
from weave.trace.serialize import from_json, to_json


def test_datetime_artifact_serialization():
    """Test that datetime objects can be serialized and deserialized using artifacts."""
    # Create a datetime object
    dt = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # Get the serializer
    dt_serializer = serializer.get_serializer_for_obj(dt)
    assert dt_serializer is not None

    # Create an artifact and serialize
    artifact = MemTraceFilesArtifact()
    dt_serializer.save(dt, artifact, "obj")

    # Deserialize
    loaded_dt = dt_serializer.load(artifact, "obj")

    # Check that the deserialized object matches the original
    assert loaded_dt.year == dt.year
    assert loaded_dt.month == dt.month
    assert loaded_dt.day == dt.day
    assert loaded_dt.hour == dt.hour
    assert loaded_dt.minute == dt.minute
    assert loaded_dt.second == dt.second
    assert loaded_dt.tzinfo is not None


def test_datetime_inline_serialization():
    """Test that datetime objects can be serialized and deserialized inline."""
    # Create a datetime object
    dt = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # Get the serializer
    dt_serializer = serializer.get_serializer_for_obj(dt)
    assert dt_serializer is not None
    assert dt_serializer.inline_serialize is not None
    assert dt_serializer.inline_deserialize is not None

    # Serialize inline
    serialized = dt_serializer.inline_serialize(dt)

    # Deserialize inline
    loaded_dt = dt_serializer.inline_deserialize(serialized)

    # Check that the deserialized object matches the original
    assert loaded_dt.year == dt.year
    assert loaded_dt.month == dt.month
    assert loaded_dt.day == dt.day
    assert loaded_dt.hour == dt.hour
    assert loaded_dt.minute == dt.minute
    assert loaded_dt.second == dt.second
    assert loaded_dt.tzinfo is not None


def test_datetime_encode_decode_custom_obj():
    """Test that datetime objects can be encoded and decoded as custom objects."""
    # Create a datetime object
    dt = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

    # Encode as custom object
    encoded = custom_objs.encode_custom_obj(dt)
    assert encoded is not None
    assert encoded["_type"] == "CustomWeaveType"
    assert encoded["weave_type"]["type"] == "datetime.datetime"

    # Check that we're using inline serialization
    assert "inline_data" in encoded
    assert "files" not in encoded

    # Decode the custom object
    decoded = custom_objs.decode_custom_obj(
        encoded["weave_type"], {}, None, encoded["inline_data"]
    )

    # Check that the decoded object matches the original
    assert decoded.year == dt.year
    assert decoded.month == dt.month
    assert decoded.day == dt.day
    assert decoded.hour == dt.hour
    assert decoded.minute == dt.minute
    assert decoded.second == dt.second
    assert decoded.tzinfo is not None


def test_datetime_to_from_json(client_creator):
    """Test that datetime objects can be serialized to and from JSON."""
    # Create a client
    with client_creator() as client:
        # Create a datetime object
        dt = datetime.datetime(2023, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

        # Serialize to JSON
        serialized = to_json(dt, client.project, client)

        # Check that we're using inline serialization
        assert serialized["_type"] == "CustomWeaveType"
        assert serialized["weave_type"]["type"] == "datetime.datetime"
        assert "inline_data" in serialized
        assert "files" not in serialized

        # Deserialize from JSON
        deserialized = from_json(serialized, client.project, client.server)

        # Check that the deserialized object matches the original
        assert deserialized.year == dt.year
        assert deserialized.month == dt.month
        assert deserialized.day == dt.day
        assert deserialized.hour == dt.hour
        assert deserialized.minute == dt.minute
        assert deserialized.second == dt.second
        assert deserialized.tzinfo is not None
