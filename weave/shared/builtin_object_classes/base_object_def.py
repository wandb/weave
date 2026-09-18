from typing import ClassVar

import pydantic

RefStr = str


# This is just an alternative to weave.Object for the server side.
# I _think_ this will go away once we have the full weave system on the server
class BaseObject(pydantic.BaseModel):
    # Validation-only schemas retain the stored inheritance chain of their SDK runtime.
    _weave_serialized_bases: ClassVar[tuple[str, ...] | None] = None

    name: str | None = None
    description: str | None = None
