import json
import weakref
from typing import Any, Optional

from weave.trace.data_structures.weak_unhashable_key_dictionary import (
    WeakKeyDictionarySupportingNonHashableKeys,
)


class CustomWeaveTypeSerializationCache:
    """A cache for custom Weave type serialization and deserialization.

    This class provides a bidirectional cache for storing and retrieving
    serialized and deserialized representations of custom Weave types.
    It uses weak references to prevent memory leaks and supports
    non-hashable objects as keys.

    Attributes:
        _obj_to_dict (WeakKeyDictionarySupportingNonHashableKeys): Maps deserialized objects to their serialized dicts.
        _dict_to_obj (weakref.WeakValueDictionary): Maps serialized dict keys to deserialized objects.
    """

    def __init__(self) -> None:
        """Initialize an empty CustomWeaveTypeSerializationCache."""
        self._obj_to_dict: WeakKeyDictionarySupportingNonHashableKeys[Any, dict] = (
            WeakKeyDictionarySupportingNonHashableKeys()
        )
        self._dict_to_obj: weakref.WeakValueDictionary[str, Any] = (
            weakref.WeakValueDictionary()
        )

    def reset(self) -> None:
        """Clear all entries from the cache."""
        self._obj_to_dict.clear()
        self._dict_to_obj.clear()

    def store(self, obj: Any, serialized_dict: dict) -> None:
        """Store a serialization pair in the cache.

        Args:
            obj: The deserialized object.
            serialized_dict: The serialized representation of the object.

        Note:
            This method silently fails if an exception occurs during storage.
        """
        try:
            self._store(obj, serialized_dict)
        except Exception:
            # TODO: Consider logging the exception here
            pass

    def _store(self, obj: Any, serialized_dict: dict) -> None:
        """Internal method to store a serialization pair.

        Args:
            obj: The deserialized object.
            serialized_dict: The serialized representation of the object.
        """
        # Remove the old serialized dict if it exists
        old_dict = self._obj_to_dict.get(obj)
        if old_dict is not None:
            old_dict_key = self._get_dict_key(old_dict)
            if old_dict_key is not None:
                self._dict_to_obj.pop(old_dict_key, None)

        # Store the new serialized dict
        self._obj_to_dict[obj] = serialized_dict
        dict_key = self._get_dict_key(serialized_dict)
        if dict_key is not None:
            self._dict_to_obj[dict_key] = obj

    def get_serialized_dict(self, obj: Any) -> Optional[dict]:
        """Retrieve the serialized dict for a given object.

        Args:
            obj: The deserialized object to look up.

        Returns:
            The serialized dict if found, None otherwise.

        Note:
            This method returns None if an exception occurs during retrieval.
        """
        try:
            return self._get_serialized_dict(obj)
        except Exception:
            # TODO: Consider logging the exception here
            return None

    def _get_serialized_dict(self, obj: Any) -> Optional[dict]:
        """Internal method to retrieve the serialized dict for an object.

        Args:
            obj: The deserialized object to look up.

        Returns:
            The serialized dict if found, None otherwise.
        """
        return self._obj_to_dict.get(obj)

    def get_deserialized_obj(self, serialized_dict: dict) -> Optional[Any]:
        """Retrieve the deserialized object for a given serialized dict.

        Args:
            serialized_dict: The serialized dict to look up.

        Returns:
            The deserialized object if found, None otherwise.

        Note:
            This method returns None if an exception occurs during retrieval.
        """
        try:
            return self._get_deserialized_obj(serialized_dict)
        except Exception:
            # TODO: Consider logging the exception here
            return None

    def _get_deserialized_obj(self, serialized_dict: dict) -> Optional[Any]:
        """Internal method to retrieve the deserialized object for a serialized dict.

        Args:
            serialized_dict: The serialized dict to look up.

        Returns:
            The deserialized object if found, None otherwise.
        """
        dict_key = self._get_dict_key(serialized_dict)
        return None if dict_key is None else self._dict_to_obj.get(dict_key)

    def _get_dict_key(self, d: dict) -> Optional[str]:
        """Generate a string key for a serialized dict.

        Args:
            d: The serialized dict.

        Returns:
            A string key if successful, None if serialization fails.
        """
        try:
            return json.dumps(d, sort_keys=True)
        except Exception:
            # TODO: Consider logging the exception here
            return None
