import json
from typing import IO, Any, Iterable, Optional, Union

from rich.table import Table

from weave.flow.prompt.common import Params, color_role
from weave.flow.prompt.message import Message
from weave.flow.prompt.placeholder import Placeholder

RenderedMessage = dict[str, Any]
RenderedMessages = list[RenderedMessage]


class Messages:
    messages: list[Message]
    placeholders: list[Placeholder]

    def __init__(self, messages: Optional[Iterable] = None):
        self.messages = []
        self.placeholders = []
        if messages:
            for message in messages:
                self.append(message)

    def append(self, message: Union[dict, Message]) -> None:
        if isinstance(message, dict):
            message = Message(**message)

        # Verify that the new message doesn't use any inconsistent placeholders
        mp = message.placeholders()
        for p in mp:
            for existing_p in self.placeholders:
                if p.name == existing_p.name:
                    if p != existing_p:
                        raise ValueError(
                            f"Duplicate placeholder with inconsistent properties: {p.name}"
                        )
        self.placeholders.extend(mp)
        self.messages.append(message)

    def with_role(self, role: str) -> "Messages":
        return Messages(m for m in self.messages if m.role == role)

    def __getitem__(self, index: int) -> Message:
        return self.messages[index]

    def __len__(self) -> int:
        return len(self.messages)

    def bind(self, params: Optional[Params] = None) -> RenderedMessages:
        return [m.bind(params) for m in self.messages]

    def to_json(self) -> list[dict[str, Any]]:
        # Don't need placeholders, they are reconstructed from messages
        return [m.to_json() for m in self.messages]

    def dump(self, fp: IO) -> None:
        json.dump(self.to_json(), fp)

    def as_rich_table(self, title: Optional[str] = None) -> Table:
        table = Table(title=title, show_header=False)
        table.add_column("Role", justify="right")
        table.add_column("Content")
        for message in self.messages:
            table.add_row(color_role(message.role), message.as_rich_str())
        return table

    @staticmethod
    def load(fp: IO) -> "Messages":
        content = json.load(fp)
        m = Messages()
        for message in content:
            m.append(Message(**message))
        return m
