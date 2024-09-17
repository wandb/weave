import json
import weakref
from typing import Any, Optional

from weave.trace.data_structures.weak_unhashable_key_dictionary import (
    WeakKeyDictionarySupportingNonHashableKeys,
)


class CustomWeaveTypeSerializationCache:
    """Cache for custom weave type serialization.

    Specifically, a dev can:
    - store a serialization tuple of (deserialized object, serialized dict)
    - retrieve the serialized dict for a deserialized object
    - retrieve the deserialized object for a serialized dict

    """

    def __init__(self) -> None:
        self._obj_to_dict: WeakKeyDictionarySupportingNonHashableKeys[Any, dict] = (
            WeakKeyDictionarySupportingNonHashableKeys()
        )
        self._dict_to_obj: weakref.WeakValueDictionary[str, Any] = (
            weakref.WeakValueDictionary()
        )

    def reset(self) -> None:
        self._obj_to_dict.clear()
        self._dict_to_obj.clear()

    def store(self, obj: Any, serialized_dict: dict) -> None:
        try:
            self._store(obj, serialized_dict)
        except Exception:
            # Consider logging the exception here
            pass

    def _store(self, obj: Any, serialized_dict: dict) -> None:
        self._obj_to_dict[obj] = serialized_dict
        dict_key = self._get_dict_key(serialized_dict)
        if dict_key is not None:
            self._dict_to_obj[dict_key] = obj

    def get_serialized_dict(self, obj: Any) -> Optional[dict]:
        try:
            return self._get_serialized_dict(obj)
        except Exception:
            # Consider logging the exception here
            return None

    def _get_serialized_dict(self, obj: Any) -> Optional[dict]:
        return self._obj_to_dict.get(obj)

    def get_deserialized_obj(self, serialized_dict: dict) -> Optional[Any]:
        try:
            return self._get_deserialized_obj(serialized_dict)
        except Exception:
            # Consider logging the exception here
            return None

    def _get_deserialized_obj(self, serialized_dict: dict) -> Optional[Any]:
        dict_key = self._get_dict_key(serialized_dict)
        return None if dict_key is None else self._dict_to_obj.get(dict_key)

    def _get_dict_key(self, d: dict) -> Optional[str]:
        try:
            return json.dumps(d, sort_keys=True)
        except Exception:
            return None
