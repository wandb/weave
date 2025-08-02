from typing import Any


class _WeaveKeyDict(dict[str, Any]):
    """A dict representing the 'weave' subdictionary of a call's attributes.

    This dictionary is not intended to be set directly.
    """

    def __setitem__(self, key: str, value: Any) -> None:
        raise KeyError("Cannot modify `weave` dict directly -- for internal use only!")

    def unwrap(self) -> dict:
        return dict(self)


class AttributesDict(dict[str, Any]):
    """A dict representing the attributes of a call.

    The ``weave`` key is reserved for internal use and cannot be set directly.
    Attributes become immutable once the call is created. Any attempt to modify
    the dictionary after call start will raise :class:`TypeError`. Use the
    :func:`weave.attributes` context manager or the ``attributes`` parameter of
    :meth:`WeaveClient.create_call` to supply metadata before the call begins.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__()
        dict.__setitem__(self, "weave", _WeaveKeyDict())

        self._frozen = False

        if kwargs:
            for key, value in kwargs.items():
                if key == "weave":
                    if isinstance(value, dict):
                        for subkey, subvalue in value.items():
                            self._set_weave_item(subkey, subvalue)
                else:
                    self[key] = value

    def freeze(self) -> None:
        self._frozen = True

    def __setitem__(self, key: str, value: Any) -> None:
        if self.__dict__.get("_frozen", False):
            raise TypeError("Cannot modify attributes after call start")
        if key == "weave":
            raise KeyError("Cannot set 'weave' directly -- for internal use only!")
        super().__setitem__(key, value)

    def __delitem__(self, key: str) -> None:
        if self.__dict__.get("_frozen", False):
            raise TypeError("Cannot modify attributes after call start")
        super().__delitem__(key)

    def update(self, *args: Any, **kwargs: Any) -> None:  # type: ignore[override]
        if self.__dict__.get("_frozen", False):
            raise TypeError("Cannot modify attributes after call start")
        for k, v in dict(*args, **kwargs).items():
            self[k] = v

    def _set_weave_item(self, subkey: str, value: Any) -> None:
        """Internal method to set items in the 'weave' subdictionary."""
        dict.__setitem__(self["weave"], subkey, value)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"

    def unwrap(self) -> dict:
        unwrapped = dict(self)
        if "weave" in unwrapped and isinstance(unwrapped["weave"], _WeaveKeyDict):
            unwrapped["weave"] = unwrapped["weave"].unwrap()
        return unwrapped
