import dataclasses
import os
import typing
import logging


ValueType = typing.TypeVar("ValueType")
ValueType2 = typing.TypeVar("ValueType2")

DEBUG = False or os.environ.get("WEAVE_VALUE_OR_ERROR_DEBUG", False)


class _ValueOrErrorInterface(typing.Generic[ValueType]):
    def unwrap(self) -> ValueType:
        raise NotImplementedError

    def transform_and_catch(
        self, fn: typing.Callable[[ValueType], ValueType2]
    ) -> "_ValueOrErrorInterface[ValueType2]":
        raise NotImplementedError

    def apply_and_catch(
        self, fn: typing.Callable[[ValueType], typing.Any]
    ) -> "_ValueOrErrorInterface[ValueType]":
        raise NotImplementedError


@dataclasses.dataclass
class Value(_ValueOrErrorInterface[ValueType]):
    _value: ValueType

    def unwrap(self) -> ValueType:
        return self._value

    def transform_and_catch(
        self, fn: typing.Callable[[ValueType], ValueType2]
    ) -> "ValueOrError[ValueType2]":
        try:
            return Value(fn(self._value))
        except Exception as e:
            return Error(e)

    def apply_and_catch(
        self, fn: typing.Callable[[ValueType], typing.Any]
    ) -> "ValueOrError[ValueType]":
        try:
            fn(self._value)
            return self
        except Exception as e:
            return Error(e)


@dataclasses.dataclass
class Error(_ValueOrErrorInterface[typing.Any]):
    _error: Exception

    def __post_init__(self) -> None:
        if DEBUG:
            raise self._error

    def unwrap(self) -> typing.Any:
        raise self._error

    def transform_and_catch(
        self, fn: typing.Callable[[typing.Any], typing.Any]
    ) -> "ValueOrError[typing.Any]":
        return self

    def apply_and_catch(
        self, fn: typing.Callable[[typing.Any], typing.Any]
    ) -> "ValueOrError[typing.Any]":
        return self


ValueOrError = typing.Union[Value[ValueType], Error]


@dataclasses.dataclass
class ValueOrErrors(typing.Generic[ValueType]):
    _items: list[ValueOrError[ValueType]] = dataclasses.field(default_factory=list)

    @classmethod
    def from_values(cls, values: list[ValueType]) -> "ValueOrErrors[ValueType]":
        return ValueOrErrors([Value(i) for i in values])

    def safe_map(
        self, fn: typing.Callable[[ValueType], ValueType2]
    ) -> "ValueOrErrors[ValueType2]":
        return ValueOrErrors([i.transform_and_catch(fn) for i in self._items])

    def raw_map(
        self,
        fn: typing.Callable[[ValueType], ValueOrError[ValueType2]],
    ) -> "ValueOrErrors[ValueType2]":
        return ValueOrErrors(
            [fn(i._value) if isinstance(i, Value) else i for i in self._items]
        )

    def safe_apply(
        self, fn: typing.Callable[[ValueType], typing.Any]
    ) -> "ValueOrErrors[ValueType]":
        return ValueOrErrors([i.apply_and_catch(fn) for i in self._items])

    def batch_map(
        self, fn: typing.Callable[[list[ValueType]], "ValueOrErrors[ValueType2]"]
    ) -> "ValueOrErrors[ValueType2]":
        valid_inputs = [i._value for i in self._items if isinstance(i, Value)]
        valid_results = fn(valid_inputs)
        valid_index = 0
        res: list[ValueOrError[ValueType2]] = []
        for i in self._items:
            if isinstance(i, Error):
                res.append(i)
            else:
                res.append(valid_results._items[valid_index])
                valid_index += 1
        return ValueOrErrors(res)

    def zip(
        self, other: "ValueOrErrors[ValueType2]"
    ) -> "ValueOrErrors[typing.Tuple[ValueType, ValueType2]]":
        res: list[ValueOrError[typing.Tuple[ValueType, ValueType2]]] = []
        for i, j in zip(self._items, other._items):
            if isinstance(i, Error):
                res.append(i)
            elif isinstance(j, Error):
                res.append(j)
            else:
                res.append(Value((i._value, j._value)))
        return ValueOrErrors(res)

    def __iter__(self) -> typing.Iterator[ValueType]:
        for i in self._items:
            yield i.unwrap()

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: int) -> ValueType:
        return self._items[index].unwrap()

    def unwrap(
        self,
    ) -> list[ValueType]:
        return list(self.__iter__())

    def iter_items(
        self,
    ) -> typing.Iterator[typing.Tuple[ValueType, typing.Optional[Exception]]]:
        for i in self._items:
            if isinstance(i, Value):
                yield i._value, None
            else:
                yield None, i._error  # type: ignore
