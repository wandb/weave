from typing import Optional

from pydantic import BaseModel


class Metadata(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
