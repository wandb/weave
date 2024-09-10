import json
import os
from pathlib import Path
from typing import IO, Any, Optional, Union

from pydantic import Field
from rich.table import Table

from weave.flow.obj import Object
from weave.flow.prompt.common import Params
from weave.flow.prompt.message import Message
from weave.flow.prompt.messages import Messages, RenderedMessages
from weave.trace import rich_pydantic_util


class Prompt(Object):
    """ """

    messages: Messages = Field(default_factory=Messages)

    def __init__(self, content: Optional[str] = None, **kwargs: Any) -> None:
        role = kwargs.pop("role", "user")
        super().__init__(**kwargs)
        if content is not None:
            self.append(content, role=role)

    def append(self, *args: Any, **kwargs: Any) -> "Prompt":
        if len(args) == 1 and len(kwargs) == 0:
            if isinstance(args[0], Message):
                message = args[0]
            elif isinstance(args[0], list):
                for item in args[0]:
                    self.append(Message(item))
                return self
            else:
                message = Message(args[0])
        else:
            message = Message(*args, **kwargs)
        self.messages.append(message)
        return self

    def append_message(self, role: str = "user") -> Message:
        message = Message(role=role)
        self.messages.append(message)
        return message

    def __getitem__(self, index: int) -> Message:
        return self.messages[index]

    def __len__(self) -> int:
        return len(self.messages)

    def to_json(self) -> dict[str, Any]:
        # TODO: Might be safer to nest this under another "messages" key
        d: dict[str, Any] = {
            "messages": self.messages.to_json(),
        }
        if self.name:
            d["name"] = self.name
        if self.description:
            d["description"] = self.description
        return d

    def bind(self, params: Optional[Params] = None) -> RenderedMessages:
        return self.messages.bind(params)

    def __call__(self, *args: Any, **kwargs: Any) -> RenderedMessages:
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
            kwargs = args[0]
        return self.bind(kwargs)

    # TODO: Any should be Dataset but there is a circular dependency issue
    def bind_rows(self, dataset: Union[list[dict], Any]) -> list[RenderedMessages]:
        rows = dataset if isinstance(dataset, list) else dataset.rows
        bound: list[RenderedMessages] = []
        for row in rows:
            bound.append(self.bind(row))
        return bound

    @staticmethod
    def from_obj(obj: Any) -> "Prompt":
        return Prompt(name=obj.name, description=obj.description, messages=obj.messages)

    @staticmethod
    def load(fp: IO) -> "Prompt":
        if isinstance(fp, str):  # Common mistake
            raise ValueError(
                "Prompt.load() takes a file-like object, not a string. Did you mean Prompt.load_file()?"
            )
        data = json.load(fp)
        prompt = Prompt()
        prompt.name = data.get("name")
        prompt.description = data.get("description")
        for message_data in data.get("messages", []):
            prompt.append(Message(**message_data))
        return prompt

    @staticmethod
    def load_file(filepath: Union[str, Path]) -> "Prompt":
        expanded_path = os.path.expanduser(str(filepath))
        with open(expanded_path, "r") as f:
            return Prompt.load(f)

    def dump(self, fp: IO) -> None:
        json.dump(self.to_json(), fp, indent=2)

    def dump_file(self, filepath: Union[str, Path]) -> None:
        expanded_path = os.path.expanduser(str(filepath))
        with open(expanded_path, "w") as f:
            self.dump(f)

    def print(self) -> str:
        tables = []
        if self.name or self.description:
            table1 = Table(show_header=False)
            table1.add_column("Key", justify="right", style="bold cyan")
            table1.add_column("Value")
            if self.name is not None:
                table1.add_row("Name", self.name)
            if self.description is not None:
                table1.add_row("Description", self.description)
            tables.append(table1)
        if self.messages:
            tables.append(self.messages.as_rich_table(title="Messages"))
        tables = [rich_pydantic_util.table_to_str(t) for t in tables]
        return "\n".join(tables)

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text("Prompt(...)")
        else:
            p.text(self.print())
