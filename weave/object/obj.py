import logging
from typing import Any, Callable, Optional, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    model_validator,
)
from typing_extensions import Self

from weave.trace import api
from weave.trace.objectify import Objectifyable
from weave.trace.op import ObjectRef, Op
from weave.trace.ref_util import get_ref
from weave.trace.vals import WeaveObject, pydantic_getattribute

logger = logging.getLogger(__name__)

T = TypeVar("T")


def deprecated_field(new_field_name: str) -> Callable[[Callable[[Any], T]], property]:
    """
    Create a deprecated property decorator that issues warnings when accessed.

    This decorator factory creates a property that acts as a deprecated alias
    for another field. When the deprecated property is accessed (either for
    getting or setting), it logs a warning message and delegates to the new
    field name.

    Args:
        new_field_name (str): The name of the new field that should be used
            instead of the deprecated one.

    Returns:
        Callable[[Callable[[Any], T]], property]: A decorator function that
            takes a method and returns a property with getter and setter that
            issue deprecation warnings.

    Example:
        ```python
        class MyClass:
            new_field: str = "value"

            @deprecated_field("new_field")
            def old_field(self) -> str:
                pass  # Implementation not used, just for type hints

        obj = MyClass()
        # This will log a warning and return "value"
        value = obj.old_field
        ```
    """

    def decorator(func: Callable[[Any], T]) -> property:
        warning_msg = f"Use `{new_field_name}` instead of `{func.__name__}`, which is deprecated and will be removed in a future version."

        def getter(self: Any) -> T:
            logger.warning(warning_msg)
            return getattr(self, new_field_name)

        def setter(self: Any, value: T) -> None:
            logger.warning(warning_msg)
            setattr(self, new_field_name, value)

        return property(fget=getter, fset=setter)

    return decorator


class Object(BaseModel):
    """
    Base class for Weave objects that can be tracked and versioned.

    This class extends Pydantic's BaseModel to provide Weave-specific functionality
    for object tracking, referencing, and serialization. Objects can have names,
    descriptions, and references that allow them to be stored and retrieved from
    the Weave system.

    Attributes:
        name (Optional[str]): A human-readable name for the object.
        description (Optional[str]): A description of what the object represents.
        ref (Optional[ObjectRef]): A reference to the object in the Weave system.

    Examples:
        ```python
        # Create a simple object
        obj = Object(name="my_object", description="A test object")

        # Create an object from a URI
        obj = Object.from_uri("weave:///entity/project/object:digest")
        ```
    """

    name: Optional[str] = None
    description: Optional[str] = None
    ref: Optional[ObjectRef] = Field(default=None, repr=False)

    # Allow Op attributes
    model_config = ConfigDict(
        ignored_types=(Op,),
        arbitrary_types_allowed=True,
        protected_namespaces=(),
        extra="forbid",
        # Intended to be used to allow "deprecated" aliases for fields until we fully remove them.
        populate_by_name=True,
    )

    __str__ = BaseModel.__repr__

    @classmethod
    def from_uri(cls, uri: str, *, objectify: bool = True) -> Self:
        """
        Create an object instance from a Weave URI.

        Args:
            uri (str): The Weave URI pointing to the object.
            objectify (bool): Whether to objectify the result. Defaults to True.

        Returns:
            Self: An instance of the class created from the URI.

        Raises:
            NotImplementedError: If the class doesn't implement the required
                methods for deserialization.

        Examples:
            ```python
            obj = MyObject.from_uri("weave:///entity/project/object:digest")
            ```
        """
        if not isinstance(cls, Objectifyable):
            raise NotImplementedError(
                f"`{cls.__name__}` must implement `from_obj` to support deserialization from a URI."
            )
        return api.ref(uri).get(objectify=objectify)

    @model_validator(mode="wrap")
    @classmethod
    def handle_relocatable_object(
        cls, v: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo
    ) -> Any:
        """
        Handle validation of relocatable objects including ObjectRef and WeaveObject.

        This validator handles special cases where the input is an ObjectRef or
        WeaveObject that needs to be properly converted to a standard Object instance.
        It ensures that references are preserved and that ignored types are handled
        correctly during the validation process.

        Args:
            v (Any): The value to validate.
            handler (ValidatorFunctionWrapHandler): The standard pydantic validation handler.
            info (ValidationInfo): Validation context information.

        Returns:
            Any: The validated object instance.

        Examples:
            This method is called automatically during object creation and validation.
            It handles cases like:
            ```python
            # When an ObjectRef is passed
            obj = MyObject(some_object_ref)

            # When a WeaveObject is passed
            obj = MyObject(some_weave_object)
            ```
        """
        if isinstance(v, ObjectRef):
            return v.get()
        if isinstance(v, WeaveObject):
            # This is a relocated object, so destructure it into a dictionary
            # so pydantic can validate it.
            keys = v._val.__dict__.keys()
            fields = {}
            for k in keys:
                if k.startswith("_"):
                    continue
                val = getattr(v, k)
                fields[k] = val

            # pydantic validation will construct a new pydantic object
            def is_ignored_type(v: type) -> bool:
                return isinstance(v, cls.model_config["ignored_types"])

            allowed_fields = {k: v for k, v in fields.items() if not is_ignored_type(v)}
            new_obj = handler(allowed_fields)
            for k, kv in fields.items():
                if is_ignored_type(kv):
                    new_obj.__dict__[k] = kv

            # transfer ref to new object
            # We can't attach a ref directly to pydantic objects yet.
            # TODO: fix this. I think dedupe may make it so the user data ends up
            #    working fine, but not setting a ref here will cause the client
            #    to do extra work.
            if isinstance(v, WeaveObject):
                ref = get_ref(v)
                new_obj.__dict__["ref"] = ref
            # return new_obj

            return new_obj
        return handler(v)


# Enable ref tracking for Weave.Object
# We could try to do this on BaseModel, but we haven't proven that's safe.
# So only Weave Objects will get ref tracking behavior for now.
Object.__getattribute__ = pydantic_getattribute  # type: ignore
