from enum import Enum
from typing import Any, Optional, TypedDict, Union
from typing_extensions import Self
from pydantic import Field
from rich.table import Table

from weave.flow.obj import Object
from weave.trace.api import publish as weave_publish
from weave.trace.objectify import register_object
from weave.trace.refs import ObjectRef
from weave.trace.vals import WeaveObject


class ReturnType(Enum):
    JSON = "json"
    TEXT = "text"
    BINARY = "binary"
    STREAM = "stream"


class ProviderConfig(TypedDict):
    base_url: str
    secret_name: str
    name: str
    extra_headers: dict[str, str]
    return_type: ReturnType


@register_object
class Provider(Object):
    base_url: str = Field(default="")
    secret_name: str = Field(default="")
    name: str = Field(default="")
    extra_headers: dict = Field(default_factory=dict)
    return_type: ReturnType = Field(default=ReturnType.JSON)

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key_name: Optional[str] = None,
        extra_headers: Optional[dict] = None,
        return_type: Optional[Union[ReturnType, str]] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        if base_url:
            self.base_url = base_url
        if description:
            self.description = description
        if api_key_name:
            self.api_key_name = api_key_name
        if name:
            self.name = name
        if extra_headers:
            self.extra_headers = extra_headers
        if return_type:
            if isinstance(return_type, str):
                self.return_type = ReturnType(return_type.lower())
            else:
                self.return_type = return_type

    def publish(self, name: Optional[str] = None) -> ObjectRef:
        return weave_publish(self, name=name)

    def config_table(self, title: Optional[str] = None) -> Table:
        table = Table(title=title, title_justify="left", show_header=False)
        table.add_column("Key", justify="right")
        table.add_column("Value")
        table.add_row("base_url", self.base_url)
        table.add_row("secret_name", self.secret_name)
        table.add_row("name", self.name)
        table.add_row("extra_headers", str(self.extra_headers))
        table.add_row("return_type", self.return_type.value)
        return table

    def print(self) -> str:
        tables = []
        if self.description:
            table = Table(show_header=False)
            table.add_column("Key", justify="right", style="bold cyan")
            table.add_column("Value")
            if self.description is not None:
                table.add_row("Description", self.description)
            tables.append(table)
        tables.append(self.config_table(title="Provider Config"))
        return "\n".join(str(t) for t in tables)

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text("Provider(...)")
        else:
            p.text(self.print())

    def as_dict(self) -> dict[str, Any]:
        return {
            "base_url": self.base_url,
            "secret_name": self.secret_name,
            "name": self.name,
            "extra_headers": self.extra_headers,
            "return_type": self.return_type.value,
        }

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        return cls(
            description=obj.description,
            ref=obj.ref,
            base_url=obj.base_url,
            secret_name=obj.secret_name,
            name=obj.name,
            extra_headers=dict(obj.extra_headers),
            return_type=obj.return_type,
        )
