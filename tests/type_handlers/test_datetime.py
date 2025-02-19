from datetime import datetime, timezone

import pytest
from PIL import Image


def test_attribute_behavior():
    # Create a small test image
    img = Image.new("RGB", (1, 1))
    # This works - PIL Image objects can have new attributes added
    img.art = "test"
    assert img.art == "test"

    # But datetime objects are immutable
    dt = datetime.now()
    with pytest.raises(AttributeError):
        dt.art = "test"


def test_datetime_serialization(client):
    # Test with timezone-aware datetime
    dt = datetime(2024, 2, 18, 12, 30, 45, tzinfo=timezone.utc)
    ref = client._save_object(dt, "my-datetime")
    loaded_dt = client.get(ref)
    assert loaded_dt == dt
    assert loaded_dt.tzinfo == timezone.utc

    # Test with naive datetime (should be converted to UTC)
    naive_dt = datetime(2024, 2, 18, 12, 30, 45)
    ref = client._save_object(naive_dt, "my-naive-datetime")
    loaded_dt = client.get(ref)
    assert loaded_dt == naive_dt.replace(tzinfo=timezone.utc)
    assert loaded_dt.tzinfo == timezone.utc
