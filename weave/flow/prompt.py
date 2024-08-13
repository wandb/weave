import json
from typing import IO, Any, Literal, Optional, Union

from pydantic import Field

from weave.flow.obj import Object

# from weave.rich_container import AbstractRichContainer


Templating = Literal["weave", "none"]

Params = dict[str, Any]

# TODO: Tighten value?
RenderedMessage = dict[str, Any]
RenderedMessages = list[RenderedMessage]


class Placeholder:
    # TODO: Limit type values
    # TODO: Add other options based on type, e.g. choices
    name: str
    type: str
    default: Optional[str]

    def __init__(
        self, name: str, type: Optional[str] = None, default: Optional[str] = None
    ):
        self.name = name
        self.type = type or "string"
        self.default = default

    def to_json(self) -> dict[str, str]:
        json_dict: dict[str, str] = {"name": self.name, "type": self.type}
        if self.default is not None:
            json_dict["default"] = self.default
        return json_dict

    def __repr__(self) -> str:
        repr_str = f"Placeholder(name='{self.name}', type='{self.type}'"
        if self.default is not None:
            repr_str += f", default='{self.default}'"
        repr_str += ")"
        return repr_str

    @staticmethod
    def from_str(s: str) -> "Placeholder":
        parts = s.split()
        name = parts[0]
        type = None
        default = None

        for part in parts[1:]:
            if part.startswith("type:"):
                type = part.split(":", 1)[1]
            elif part.startswith("default:"):
                default = part.split(":", 1)[1]

        return Placeholder(name=name, type=type, default=default)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Placeholder):
            return False
        return (
            self.name == other.name
            and self.type == other.type
            and self.default == other.default
        )

    def __hash__(self):
        return hash((self.name, self.type, self.default))


MessagePart = Union[str, Placeholder]


class MessageParts:
    parts: list[MessagePart]

    def __init__(self, parts: Optional[list[MessagePart]] = None):
        self.parts = parts or []

    def placeholders(self) -> list[Placeholder]:
        return [part for part in self.parts if isinstance(part, Placeholder)]

    def bind(self, params: Params) -> str:
        bound_parts = []
        for part in self.parts:
            if isinstance(part, Placeholder):
                if part.name in params:
                    bound_parts.append(params[part.name])
                elif part.default is not None:
                    bound_parts.append(part.default)
                else:
                    raise ValueError(f"Missing value for placeholder: {part.name}")
            else:
                bound_parts.append(part)
        return "".join(bound_parts)

    def to_json(self) -> list[Union[str, dict[str, str]]]:
        return [
            part.to_json() if isinstance(part, Placeholder) else part
            for part in self.parts
        ]

    @staticmethod
    def from_list(l: list) -> "MessageParts":
        parts = []
        for item in l:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(Placeholder(**item))
        return MessageParts(parts)

    @staticmethod
    def from_str(s: str, templating: Templating = "weave") -> "MessageParts":
        parts = []
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


# TODO: Restrict more

Detail = Literal["low", "high", "auto"]


class Message:
    content: MessageParts
    messages: list[dict]
    role: str
    templating: Templating

    def __init__(
        self,
        content: Optional[Union[str, list]] = None,
        role: str = "user",
        templating: Templating = "weave",
    ):
        self.templating = templating
        self.role = role
        if isinstance(content, list):
            self.content = MessageParts.from_list(content)
        else:
            self.content = MessageParts.from_str(content, templating)
        # TODO: need to be able to init messages too
        self.messages = []

    def bind(self, params: Optional[Params] = None) -> dict[str, Any]:
        params = params or {}
        bound = {"role": self.role}
        if self.content:
            bound["content"] = self.content.bind(params)
        if self.messages:
            # TODO: Support messages with placeholders
            bound["content"] = self.messages
            # for message in self.messages:
            #     if message["type"] == "text":
            #         bound["content"].append({"type": "text", "text": bind_placeholders(message["text"], params, self.placeholders)})
            #     elif message["type"] == "image_url":
            #         bound["content"].append(message)
        return bound

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
        d = {
            "role": self.role,
        }
        if self.content is not None:
            d["content"] = self.content.to_json()
        if self.messages:
            d["content"] = self.messages
        return d

    def __repr__(self) -> str:
        # content_preview = self.content[:30] + "..." if self.content else ""
        # multi_message_count = len(self.messages)
        return f"Message(role='{self.role}', content='{self.content}'"


class Messages:
    messages: list[Message]
    placeholders: list[Placeholder]

    def __init__(self):
        self.messages = []
        self.placeholders = []

    def append(self, message: Message):
        mp = message.placeholders()
        for p in mp:
            for existing_p in self.placeholders:
                if p.name == existing_p.name:
                    if p != existing_p:
                        raise ValueError(
                            f"Duplicate placeholder with inconsistent properties: {p.name}"
                        )
        # TODO: Validate that no inconsistent placeholders are used
        self.placeholders.extend(mp)
        self.messages.append(message)

    def __getitem__(self, index: int) -> Message:
        return self.messages[index]

    def __len__(self) -> int:
        return len(self.messages)

    def bind(self, params: Optional[Params] = None) -> RenderedMessages:
        return [m.bind(params) for m in self.messages]

    def to_json(self) -> list[dict[str, Any]]:
        return {
            "messages": [m.to_json() for m in self.messages],
            "placeholders": [p.to_json() for p in self.placeholders],
        }

    def dump(self, fp: IO[str]) -> None:
        json.dump(self.to_json(), fp)

    @staticmethod
    def load(fp: IO[str]) -> "Messages":
        content = json.load(fp)
        # print(content)
        m = Messages()
        for message in content["messages"]:
            m.append(Message(**message))
        return m


class Prompt(Object):
    """ """

    messages: Messages = Field(default_factory=Messages)

    # def __init__(self, **data):
    #     super().__init__(**data)
    def append(self, *args, **kwargs) -> "Prompt":
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], Message):
            message = args[0]
        else:
            message = Message(*args, **kwargs)
        self.messages.append(message)
        return self

    #         # print("prompt init")
    #         # print(data)
    #         # if 'messages' not in data:
    #         #     data['messages'] = Messages()
    # #        self.messages = []

    #     def append(self, content: Optional[str] = None, role: str = "user", *, placeholders: Templating = "weave") -> 'Prompt':
    #         # TODO: validate
    #         message = {
    #             "role": role,
    #             "placeholders": placeholders
    #         }
    #         if content is not None:
    #             message["content"] = content
    #         self.messages.append(message)
    #         return self

    def append_message(self, role: str = "user") -> Message:
        message = Message(role=role)
        self.messages.append(message)
        return message

    #     def __iter__(self) -> Iterator[Message]:
    #         for message in self.messages:
    #             yield Message(**message)

    def __getitem__(self, index: int) -> Message:
        return self.messages[index]

    def __len__(self) -> int:
        return len(self.messages)

    def to_json(self) -> dict:
        # TODO: Might be safer to nest this under another "messages" key
        return self.messages.to_json()

    def bind(self, params: Optional[Params] = None) -> RenderedMessages:
        return self.messages.bind(params)

    def __call__(self, *args, **kwargs) -> RenderedMessages:
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
            kwargs = args[0]
        return self.bind(kwargs)

    @staticmethod
    def from_obj(obj: Any) -> "Prompt":
        return Prompt(name=obj.name, description=obj.description, messages=obj.messages)
