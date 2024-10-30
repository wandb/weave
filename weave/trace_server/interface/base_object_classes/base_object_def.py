from typing import Optional

import pydantic

RefStr = str


class BaseObject(pydantic.BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
