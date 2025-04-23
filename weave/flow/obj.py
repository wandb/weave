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
        if not isinstance(cls, Objectifyable):
            raise NotImplementedError(
                f"`{cls.__name__}` must implement `from_obj` to support deserialization from a URI."
            )
        return api.ref(uri).get(objectify=objectify)

    # This is a "wrap" validator meaning we can run our own logic before
    # and after the standard pydantic validation.
    @model_validator(mode="wrap")
    @classmethod
    def handle_relocatable_object(
        cls, v: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo
    ) -> Any:
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
