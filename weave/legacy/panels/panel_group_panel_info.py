from __future__ import annotations
from typing_extensions import (
    NotRequired,
    TypedDict,
)

# In own file so we can use future annotations (NotRequired)


class PanelInfo(TypedDict):
    hidden: NotRequired[bool]
