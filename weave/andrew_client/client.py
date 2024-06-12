from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from weave.trace_server.trace_server_interface import TraceServerInterface


class PromoteEmbeddedInterfaceMethodsMeta(type):
    """Metaclass that promotes methods from embedded interfaces to the top level.

    This behaviour is similar to embedding interfaces in Go."""

    def __new__(cls, name, bases, dct):
        new_cls = super().__new__(cls, name, bases, dct)

        # Inspect annotations to find delegate attributes
        annotations = dct.get("__annotations__", {})

        for attr, attr_type in annotations.items():
            if isinstance(attr_type, type) and issubclass(attr_type, Protocol):
                # Add delegating methods for each protocol method
                for method_name in attr_type.__dict__:
                    if not method_name.startswith("_") and method_name not in dct:

                        def make_delegate_method(attr, method_name):
                            def method(self, *args, **kwargs):
                                return getattr(getattr(self, attr), method_name)(*args, **kwargs)

                            method.__name__ = method_name
                            return method

                        setattr(new_cls, method_name, make_delegate_method(attr, method_name))

        return new_cls


@runtime_checkable
class Calls(Protocol):
    # Use whatever server (or none?) to implement the below

    def get_call(self): ...
    def create_call(self): ...
    def finish_call(self): ...
    def fail_call(self): ...
    def delete_call(self): ...


@runtime_checkable
class Objects(Protocol):
    def get_object(self): ...
    def create_object(self): ...


@runtime_checkable
class WeaveApi(Calls, Objects): ...


@dataclass
class EverythingApi(metaclass=PromoteEmbeddedInterfaceMethodsMeta):
    """This API brings together all the sub-apis and promotes their methods to the top level.

    api = EverythingApi(
        calls=ConcreteCalls(),
        objects=ConcreteObjects(),
        ...
    )

    api.get_call(...)  # this is delegated to api.calls.get_call(...)
    """

    calls: Calls
    objects: Objects
    ...

    @classmethod
    def with_clickhouse_backend(cls):
        return cls(
            calls=RemoteHTTPTraceServerCalls(),
            objects=RemoteHTTPTraceServerObjects(),
        )

    @classmethod
    def with_local_backend(cls):
        return cls(
            calls=SqliteServerCalls(),
            objects=SqliteServerObjects(),
        )

    @classmethod
    def with_some_weird_mixture(cls):
        return cls(
            calls=RemoteHTTPTraceServerCalls(),
            objects=SqliteServerObjects(),
        )


@dataclass
class Client:
    entity: str
    project: str
    api: WeaveApi

    # TODO: add convenience methods here
    def get(self, ref): ...
    def save(self, val, name, branch): ...


def init_client():
    api = EverythingApi()
