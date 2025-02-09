from typing import Optional

import pydantic

RefStr = str


# This is just an alternative to weave.Object for the server side.
# I _think_ this will go away once we have the full weave system on the server
class BaseObject(pydantic.BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
