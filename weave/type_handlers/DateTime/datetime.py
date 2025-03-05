import datetime

from weave.trace.serialization import serializer


def save(obj: datetime.datetime) -> str:
    """Serialize a datetime object to ISO format with timezone information.
    If the datetime object is naive (has no timezone), it will be assumed to be UTC.

    TODO: Should we attempt to get local timezone information and save that too?
    """
    if obj.tzinfo is None:
        obj = obj.replace(tzinfo=datetime.timezone.utc)
    return obj.isoformat()


def load(encoded: str) -> datetime.datetime:
    """Deserialize an ISO format string back to a datetime object with timezone."""
    return datetime.datetime.fromisoformat(encoded)


def register() -> None:
    serializer.register_serializer(datetime.datetime, save, load)
