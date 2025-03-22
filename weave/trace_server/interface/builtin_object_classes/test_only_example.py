from pydantic import BaseModel

from weave.trace_server.interface.builtin_object_classes import base_object_def


class NestedBaseModelForTesting(BaseModel):
    a: int


class NestedBaseObjectForTesting(base_object_def.BaseObject):
    b: int


class ExampleForTesting(base_object_def.BaseObject):
    primitive: int
    nested_base_model: NestedBaseModelForTesting
    # Important: `RefStr` is just an alias for `str`. When defining `BaseObject`s, we
    # should never have a property point to another `BaseObject`. This is because each
    # base object is stored in the database and should be treated like a foreign key.
    #
    # It would be nice to have a way to ensure that no `BaseObject` has any `BaseObject`
    # properties.
    nested_base_object: base_object_def.RefStr


__all__ = ["ExampleForTesting", "NestedBaseObjectForTesting"]
