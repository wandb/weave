import weakref
from typing import Any, Generic, Iterator, Tuple, TypeVar, Union, ValuesView

K = TypeVar("K")
V = TypeVar("V")


class WeakKeyDictionarySupportingNonHashableKeys(Generic[K, V]):
    """
    A dictionary-like data structure that supports weak references to keys,
    including non-hashable objects.

    This class is similar to `weakref.WeakKeyDictionary`, but it can handle
    keys that are not hashable. It uses the object's id as a proxy for hashing,
    allowing it to store and retrieve items based on object identity rather than
    hash value.

    The keys are held using weak references, which means that when there are no
    other references to a key object, it will be garbage collected, and its
    corresponding entry will be automatically removed from this dictionary.

    This implementation uses the `weakref.finalize` method to ensure that entries
    are removed from the internal maps when a key object is garbage collected.
    This approach effectively prevents issues related to id reuse, as the entry
    for a specific id is guaranteed to be removed before that id could potentially
    be reused for a new object.

    Type Parameters:
    K: The type of the keys (can be any object, including non-hashable ones)
    V: The type of the values

    Note: While this implementation mitigates the risk of id collisions due to
    garbage collection and id reuse, it's important to remember that object ids
    in Python are not guaranteed to be unique over the lifetime of a program.
    However, for most practical purposes, this implementation provides a robust
    solution for weak key dictionaries supporting non-hashable keys.
    """

    def __init__(self) -> None:
        """Initialize an empty WeakKeyDictionarySupportingNonHashableKeys."""
        self._id_to_data: dict[int, V] = {}
        self._id_to_key: weakref.WeakValueDictionary[int, K] = (
            weakref.WeakValueDictionary()
        )

    def clear(self) -> None:
        """Remove all items from the dictionary."""
        self._id_to_data.clear()
        self._id_to_key.clear()

    def get(self, key: K, default: Any = None) -> Union[V, Any]:
        """
        Return the value for key if key is in the dictionary, else default.

        Args:
            key (K): The key to look up.
            default (Any, optional): The value to return if the key is not found.
                Defaults to None.

        Returns:
            Union[V, Any]: The value associated with the key, or the default value.
        """
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def __getitem__(self, key: K) -> V:
        """
        Return the value associated with the given key.

        Args:
            key (K): The key to look up.

        Returns:
            V: The value associated with the key.

        Raises:
            KeyError: If the key is not found in the dictionary.
        """
        item_id = id(key)
        return self._id_to_data[item_id]

    def __delitem__(self, key: K) -> None:
        """
        Remove the item with the given key from the dictionary.

        Args:
            key (K): The key of the item to remove.

        Raises:
            KeyError: If the key is not found in the dictionary.
        """
        item_id = id(key)
        if item_id in self._id_to_data:
            del self._id_to_data[item_id]
            del self._id_to_key[item_id]
        else:
            raise KeyError(key)

    def __setitem__(self, key: K, value: V) -> None:
        """
        Set the value for the given key in the dictionary.

        This method also sets up a weak reference to the key object,
        so that the item will be automatically removed when the key
        object is garbage collected.

        Args:
            key (K): The key to set.
            value (V): The value to associate with the key.
        """
        item_id = id(key)
        self._id_to_data[item_id] = value
        self._id_to_key[item_id] = key
        weakref.finalize(key, self._remove_item, item_id)

    def _remove_item(self, item_id: int) -> None:
        """
        Remove an item from the dictionary based on its id.

        This method is called by the weak reference callback when a key
        object is garbage collected.

        Args:
            item_id (int): The id of the item to remove.
        """
        self._id_to_data.pop(item_id, None)
        self._id_to_key.pop(item_id, None)

    def __iter__(self) -> Iterator[K]:
        """
        Return an iterator over the keys in the dictionary.

        Returns:
            Iterator[K]: An iterator yielding the dictionary's keys.
        """
        return iter(self._id_to_key.values())

    def __len__(self) -> int:
        """
        Return the number of items in the dictionary.

        Returns:
            int: The number of items in the dictionary.
        """
        return len(self._id_to_data)

    def keys(self) -> Iterator[K]:
        """
        Return a view of the dictionary's keys.

        Returns:
            Iterator[K]: A view object providing a view on the dictionary's keys.
        """
        return self._id_to_key.values()

    def values(self) -> ValuesView[V]:
        """
        Return a view of the dictionary's values.

        Returns:
            ValuesView[V]: A view object providing a view on the dictionary's values.
        """
        return self._id_to_data.values()

    def items(self) -> Iterator[Tuple[K, V]]:
        """
        Return an iterator over the dictionary's items (key-value pairs).

        Returns:
            Iterator[Tuple[K, V]]: An iterator yielding (key, value) pairs.
        """
        return ((self._id_to_key[id], value) for id, value in self._id_to_data.items())
