"""A message is a single unit of communication with an associated role."""

from typing import Any, Literal, Optional, Union

from weave.flow.prompt.common import Params, Templating
from weave.flow.prompt.placeholder import Placeholder

MessagePart = Union[str, Placeholder]


class MessageParts:
    parts: list[MessagePart]

    def __init__(self, parts: Optional[list[MessagePart]] = None):
        self.parts = parts or []

    def placeholders(self) -> list[Placeholder]:
        return [part for part in self.parts if isinstance(part, Placeholder)]

    def copy(self) -> "MessageParts":
        """Create a deep copy of the MessageParts object."""
        new_parts = []
        for part in self.parts:
            if isinstance(part, Placeholder):
                new_parts.append(part.copy())
            else:
                new_parts.append(part)
        return MessageParts(new_parts)

    def bind(self, params: Params) -> str:
        missing = set()
        bound_parts = []
        for part in self.parts:
            if isinstance(part, Placeholder):
                # TODO: Support formatting of value?
                if part.name in params:
                    bound_parts.append(str(params[part.name]))
                elif part.default is not None:
                    bound_parts.append(str(part.default))
                else:
                    missing.add(part.name)
            else:
                bound_parts.append(part)
        if missing:
            raise ValueError(f"Missing values for placeholders: {', '.join(missing)}")

        return "".join(bound_parts)

    def to_json(self) -> str:
        return "".join(
            p.as_str() if isinstance(p, Placeholder) else p for p in self.parts
        )

    @staticmethod
    def from_list(l: list) -> "MessageParts":
        parts: list[MessagePart] = []
        for item in l:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(Placeholder(**item))
        return MessageParts(parts)

    @staticmethod
    def from_str(s: str, templating: Templating = "weave") -> "MessageParts":
        parts: list[MessagePart] = []
        if not s:
            return MessageParts()

        if templating == "none":
            return MessageParts([s])

        part = ""
        escaped = False
        in_placeholder = False
        for char in s:
            if char == "\\":
                escaped = True
                continue
            if escaped:
                part += char
                escaped = False
                continue
            if char == "{":
                in_placeholder = True
                if part:
                    parts.append(part)
                    part = ""
                continue
            if char == "}":
                in_placeholder = False
                parts.append(Placeholder.from_str(part))
                part = ""
                continue
            part += char

        if escaped:
            raise ValueError("String cannot end with escape character")
        if in_placeholder:
            raise ValueError("Unterminated placeholder")
        if part:
            parts.append(part)
        return MessageParts(parts)

    def __repr__(self) -> str:
        return f"MessageParts(parts={self.parts})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MessageParts):
            return NotImplemented
        return self.parts == other.parts

    def as_str(self, join_str: str = " ") -> str:
        return join_str.join(
            p.as_str() if isinstance(p, Placeholder) else p for p in self.parts
        )

    def as_rich_str(self) -> str:
        rich_parts = []
        for part in self.parts:
            if isinstance(part, Placeholder):
                rich_parts.append(part.as_rich_str())
            else:
                rich_parts.append(part)
        return "".join(rich_parts)


# TODO: Restrict more

Detail = Literal["low", "high", "auto"]


class Message:
    content: MessageParts
    messages: list[dict]
    role: str
    templating: Templating

    def __init__(
        self,
        content: Optional[Union[str, dict, list]] = None,
        role: str = "user",
        templating: Templating = "weave",
    ):
        self.templating = templating
        self.role = role
        if isinstance(content, list):
            self.content = MessageParts.from_list(content)
        elif isinstance(content, dict):
            # Would it be better to throw if content is missing?
            self.role = content.get("role", role)
            self.content = MessageParts([content.get("content", "")])
        else:
            self.content = MessageParts.from_str(content or "", templating)
        # TODO: need to be able to init messages too
        self.messages = []

    def bind(self, params: Optional[Params] = None) -> dict[str, Any]:
        params = params or {}
        bound: dict[str, Any] = {"role": self.role}
        if self.content:
            bound["content"] = self.content.bind(params)
        if self.messages:
            # TODO: Support messages with placeholders
            bound["content"] = self.messages
        return bound

    def copy(self) -> "Message":
        """Create a deep copy of the Message object."""
        new_message = Message(role=self.role, templating=self.templating)
        new_message.content = self.content.copy()
        new_message.messages = [message.copy() for message in self.messages]
        return new_message

    def add_text(self, text: str) -> "Message":
        self.messages.append({"type": "text", "text": text})
        return self

    def add_image_url(self, url: str, detail: Optional[Detail] = None) -> "Message":
        image_url = dict(url=url)
        if detail:
            image_url["detail"] = detail
        self.messages.append({"type": "image_url", "image_url": image_url})
        return self

    def placeholders(self) -> list[Placeholder]:
        # TODO: Support placeholders in messages
        return self.content.placeholders()

    def to_json(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "role": self.role,
        }
        if self.content is not None:
            d["content"] = self.content.to_json()
        if self.messages:
            d["content"] = self.messages
        return d

    def __repr__(self) -> str:
        return f"Message(role='{self.role}', content='{self.content}'"

    def as_str(self, join_str: str = " ") -> str:
        return self.content.as_str(join_str)

    def as_rich_str(self) -> str:
        # TODO: Messages
        return self.content.as_rich_str()
