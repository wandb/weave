from pydantic import BaseModel, Field

from weave.trace_server.interface.builtin_object_classes import base_object_def


class TestOnlyNestedBaseModel(BaseModel):
    a: int
    aliased_property: int = Field(alias="aliased_property_alias")


class TestOnlyNestedBaseObject(base_object_def.BaseObject):
    b: int


class TestOnlyExample(base_object_def.BaseObject):
    primitive: int
    nested_base_model: TestOnlyNestedBaseModel
    # Important: `RefStr` is just an alias for `str`. When defining `BaseObject`s, we
    # should never have a property point to another `BaseObject`. This is because each
    # base object is stored in the database and should be treated like a foreign key.
    #
    # It would be nice to have a way to ensure that no `BaseObject` has any `BaseObject`
    # properties.
    nested_base_object: base_object_def.RefStr


__all__ = ["TestOnlyExample", "TestOnlyNestedBaseObject"]
