import copy
import json
import os
import re
import textwrap
from collections import UserList
from pathlib import Path
from typing import IO, Any, Optional, SupportsIndex, TypedDict, Union, cast, overload

from pydantic import Field
from rich.table import Table
from typing_extensions import Self

from weave.flow.obj import Object
from weave.flow.prompt.common import ROLE_COLORS, color_role
from weave.trace.api import publish as weave_publish
from weave.trace.objectify import register_object
from weave.trace.op import op
from weave.trace.refs import ObjectRef
from weave.trace.rich import pydantic_util
from weave.trace.vals import WeaveObject


class Message(TypedDict):
    role: str
    content: str


def maybe_dedent(content: str, dedent: bool) -> str:
    if dedent:
        return textwrap.dedent(content).strip()
    return content


def str_to_message(
    content: str, role: Optional[str] = None, dedent: bool = False
) -> Message:
    if role is not None:
        return {"role": role, "content": maybe_dedent(content, dedent)}
    for role in ROLE_COLORS:
        prefix = role + ":"
        if content.startswith(prefix):
            return {
                "role": role,
                "content": maybe_dedent(content[len(prefix) :].lstrip(), dedent),
            }
    return {"role": "user", "content": maybe_dedent(content, dedent)}


# TODO: This supports Python format specifiers, but maybe we don't want to
#       because it will be harder to do in clients in other languages?
RE_PLACEHOLDER = re.compile(r"\{(\w+)(:[^}]+)?\}")


def extract_placeholders(text: str) -> list[str]:
    placeholders = re.findall(RE_PLACEHOLDER, text)
    unique = []
    for name, _ in placeholders:
        if name not in unique:
            unique.append(name)
    return unique


def color_content(content: str, values: dict) -> str:
    placeholders = extract_placeholders(content)
    colored_values = {}
    for placeholder in placeholders:
        if placeholder not in values:
            colored_values[placeholder] = "[red]{" + placeholder + "}[/]"
        else:
            colored_values[placeholder] = (
                "[orange3]{" + placeholder + ":" + str(values[placeholder]) + "}[/]"
            )
    return content.format(**colored_values)


class Prompt(Object):
    def format(self, **kwargs: Any) -> Any:
        raise NotImplementedError("Subclasses must implement format()")


@register_object
class StringPrompt(Prompt):
    content: str = ""

    def __init__(self, content: str):
        super().__init__()
        self.content = content

    def format(self, **kwargs: Any) -> str:
        return self.content.format(**kwargs)

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        prompt = cls(content=obj.content)
        prompt.name = obj.name
        prompt.description = obj.description
        prompt.ref = cast(ObjectRef, obj.ref)
        return prompt


@register_object
class MessagesPrompt(Prompt):
    messages: list[dict] = Field(default_factory=list)

    def __init__(self, messages: list[dict]):
        super().__init__()
        self.messages = messages

    def format_message(self, message: dict, **kwargs: Any) -> dict:
        m = {}
        for k, v in message.items():
            if isinstance(v, str):
                m[k] = v.format(**kwargs)
            else:
                m[k] = v
        return m

    def format(self, **kwargs: Any) -> list:
        return [self.format_message(m, **kwargs) for m in self.messages]

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        prompt = cls(messages=obj.messages)
        prompt.name = obj.name
        prompt.description = obj.description
        prompt.ref = cast(ObjectRef, obj.ref)
        return prompt


@register_object
class EasyPrompt(UserList, Prompt):
    data: list = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    requirements: dict = Field(default_factory=dict)

    _values: dict

    def __init__(
        self,
        content: Optional[Union[str, dict, list]] = None,
        *,
        role: Optional[str] = None,
        dedent: bool = False,
        **kwargs: Any,
    ) -> None:
        super(UserList, self).__init__()
        name = kwargs.pop("name", None)
        description = kwargs.pop("description", None)
        config = kwargs.pop("config", {})
        requirements = kwargs.pop("requirements", {})
        if "messages" in kwargs:
            content = kwargs.pop("messages")
            config.update(kwargs)
            kwargs = {"config": config, "requirements": requirements}
        super(Object, self).__init__(name=name, description=description, **kwargs)
        self._values = {}
        if content is not None:
            if isinstance(content, (str, dict)):
                content = [content]
            for item in content:
                self.append(item, role=role, dedent=dedent)

    def __add__(self, other: Any) -> "Prompt":
        new_prompt = self.copy()
        new_prompt += other
        return new_prompt

    def append(
        self,
        item: Any,
        role: Optional[str] = None,
        dedent: bool = False,
    ) -> None:
        if isinstance(item, str):
            # Seems like we don't want to do this, if the user wants
            # all system we have helpers for that, and we want to make the
            # case of constructing system + user easy
            # role = self.data[-1].get("role", "user") if self.data else "user"
            self.data.append(str_to_message(item, role=role, dedent=dedent))
        elif isinstance(item, dict):
            # TODO: Validate that item has message shape
            # TODO: Override role and do dedent?
            self.data.append(item)
        elif isinstance(item, list):
            for item in item:
                self.append(item)
        else:
            raise TypeError(f"Cannot append {item} of type {type(item)} to Prompt")

    def __iadd__(self, item: Any) -> "Prompt":
        self.append(item)
        return self

    @property
    def as_str(self) -> str:
        """Join all messages into a single string."""
        return " ".join(message.get("content", "") for message in self.data)

    @property
    def system_message(self) -> Message:
        """Join all messages into a system prompt message."""
        return {"role": "system", "content": self.as_str}

    @property
    def system_prompt(self) -> "Prompt":
        """Join all messages into a system prompt object."""
        return Prompt(self.as_str, role="system")

    @property
    def messages(self) -> list[Message]:
        return self.data

    @property
    def placeholders(self) -> list[str]:
        all_placeholders: list[str] = []
        for message in self.data:
            # TODO: Support placeholders in image messages?
            placeholders = extract_placeholders(message["content"])
            all_placeholders.extend(
                p for p in placeholders if p not in all_placeholders
            )
        return all_placeholders

    @property
    def unbound_placeholders(self) -> list[str]:
        unbound = []
        for p in self.placeholders:
            if p not in self._values:
                unbound.append(p)
        return unbound

    @property
    def is_bound(self) -> bool:
        return not self.unbound_placeholders

    def validate_requirement(self, key: str, value: Any) -> list:
        problems = []
        requirement = self.requirements.get(key)
        if not requirement:
            return []
        # TODO: Type coercion
        min = requirement.get("min")
        if min is not None and value < min:
            problems.append(f"{key} ({value}) is less than min ({min})")
        max = requirement.get("max")
        if max is not None and value > max:
            problems.append(f"{key} ({value}) is greater than max ({max})")
        oneof = requirement.get("oneof")
        if oneof is not None and value not in oneof:
            problems.append(f"{key} ({value}) must be one of {', '.join(oneof)}")
        return problems

    def validate_requirements(self, values: dict[str, Any]) -> list:
        problems = []
        for key, value in values.items():
            problems += self.validate_requirement(key, value)
        return problems

    def bind(self, *args: Any, **kwargs: Any) -> "Prompt":
        is_dict = len(args) == 1 and isinstance(args[0], dict)
        problems = []
        if is_dict:
            problems += self.validate_requirements(args[0])
        problems += self.validate_requirements(kwargs)
        if problems:
            raise ValueError("\n".join(problems))
        if is_dict:
            self._values.update(args[0])
        self._values.update(kwargs)
        return self

    def __call__(self, *args: Any, **kwargs: Any) -> list[Message]:
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
            kwargs = args[0]
        prompt = self.bind(kwargs)
        return list(prompt)

    # TODO: Any should be Dataset but there is a circular dependency issue
    def bind_rows(self, dataset: Union[list[dict], Any]) -> list["Prompt"]:
        rows = dataset if isinstance(dataset, list) else dataset.rows
        bound: list[Prompt] = []
        for row in rows:
            bound.append(self.copy().bind(row))
        return bound

    @overload
    def __getitem__(self, key: SupportsIndex) -> Any: ...

    @overload
    def __getitem__(self, key: slice) -> "EasyPrompt": ...

    def __getitem__(self, key: Union[SupportsIndex, slice]) -> Any:
        """Override getitem to return a Message, Prompt object, or config value."""
        if isinstance(key, SupportsIndex):
            int_index = key.__index__()
            message = self.data[int_index].copy()
            placeholders = extract_placeholders(message["content"])
            values = {}
            for placeholder in placeholders:
                if placeholder in self._values:
                    values[placeholder] = self._values[placeholder]
                elif (
                    placeholder in self.requirements
                    and "default" in self.requirements[placeholder]
                ):
                    values[placeholder] = self.requirements[placeholder]["default"]
                else:
                    values[placeholder] = "{" + placeholder + "}"
            message["content"] = message["content"].format(**values)
            return message
        elif isinstance(key, slice):
            new_prompt = Prompt()
            new_prompt.name = self.name
            new_prompt.description = self.description
            new_prompt.data = self.data[key]
            new_prompt.config = self.config.copy()
            new_prompt.requirements = self.requirements.copy()
            new_prompt._values = self._values.copy()
            return new_prompt
        elif isinstance(key, str):
            if key == "ref":
                return self
            if key == "messages":
                return self.data
            return self.config[key]
        else:
            raise TypeError(f"Invalid argument type: {type(key)}")

    def __deepcopy__(self, memo: dict) -> "Prompt":
        # I'm sure this isn't right, but hacking in to avoid
        # TypeError: cannot pickle '_thread.lock' object.
        # Basically, as part of logging our message objects are
        # turning into WeaveDicts which have a sever reference which
        # in turn can't be copied
        c = copy.deepcopy(dict(self.config), memo)
        r = copy.deepcopy(dict(self.requirements), memo)
        p = Prompt(
            name=self.name, description=self.description, config=c, requirements=r
        )
        p._values = dict(self._values)
        for value in self.data:
            p.data.append(dict(value))
        return p

    def require(self, param_name: str, **kwargs: Any) -> "Prompt":
        self.requirements[param_name] = kwargs
        return self

    def configure(self, config: Optional[dict] = None, **kwargs: Any) -> "Prompt":
        if config:
            self.config = config
        self.config.update(kwargs)
        return self

    def publish(self, name: Optional[str] = None) -> ObjectRef:
        # TODO: This only works if we've called weave.init, but it seems like
        #       that shouldn't be necessary if we have loaded this from a ref.
        return weave_publish(self, name=name)

    def messages_table(self, title: Optional[str] = None) -> Table:
        table = Table(title=title, title_justify="left", show_header=False)
        table.add_column("Role", justify="right")
        table.add_column("Content")
        # TODO: Maybe we should inline the values here? Or highlight placeholders missing values in red?
        for message in self.data:
            table.add_row(
                color_role(message.get("role", "user")),
                color_content(message.get("content", ""), self._values),
            )
        return table

    def values_table(self, title: Optional[str] = None) -> Table:
        table = Table(title=title, title_justify="left", show_header=False)
        table.add_column("Parameter", justify="right")
        table.add_column("Value")
        for key, value in self._values.items():
            table.add_row(key, str(value))
        return table

    def config_table(self, title: Optional[str] = None) -> Table:
        table = Table(title=title, title_justify="left", show_header=False)
        table.add_column("Key", justify="right")
        table.add_column("Value")
        for key, value in self.config.items():
            table.add_row(key, str(value))
        return table

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
        if self.data:
            tables.append(self.messages_table(title="Messages"))
        if self._values:
            tables.append(self.values_table(title="Parameters"))
        if self.config:
            tables.append(self.config_table(title="Config"))
        tables = [pydantic_util.table_to_str(t) for t in tables]
        return "\n".join(tables)

    def __str__(self) -> str:
        """Return a single prompt string when str() is called on the object."""
        return self.as_str

    def _repr_pretty_(self, p: Any, cycle: bool) -> None:
        """Show a nicely formatted table in ipython."""
        if cycle:
            p.text("Prompt(...)")
        else:
            p.text(self.print())

    def as_pydantic_dict(self) -> dict[str, Any]:
        return self.model_dump()

    def as_dict(self) -> dict[str, Any]:
        # In chat completion kwargs format
        return {
            **self.config,
            "messages": list(self),
        }

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        messages = obj.messages if hasattr(obj, "messages") else obj.data
        messages = [dict(m) for m in messages]
        config = dict(obj.config)
        requirements = dict(obj.requirements)
        return cls(
            name=obj.name,
            description=obj.description,
            ref=obj.ref,
            messages=messages,
            config=config,
            requirements=requirements,
        )

    @classmethod
    def load(cls, fp: IO) -> Self:
        if isinstance(fp, str):  # Common mistake
            raise TypeError(
                "Prompt.load() takes a file-like object, not a string. Did you mean Prompt.e()?"
            )
        data = json.load(fp)
        prompt = EasyPrompt(**data)
        return prompt

    @classmethod
    def load_file(cls, filepath: Union[str, Path]) -> Self:
        expanded_path = os.path.expanduser(str(filepath))
        with open(expanded_path) as f:
            return EasyPrompt.load(f)

    def dump(self, fp: IO) -> None:
        json.dump(self.as_pydantic_dict(), fp, indent=2)

    def dump_file(self, filepath: Union[str, Path]) -> None:
        expanded_path = os.path.expanduser(str(filepath))
        with open(expanded_path, "w") as f:
            self.dump(f)

    # TODO: We would like to be able to make this an Op.
    # Unfortunately, litellm tries to make a deepcopy of the messages
    # and that fails because the Message objects aren't picklable.
    # TypeError: cannot pickle '_thread.RLock' object
    # (Which I think is because they keep a reference to the server interface maybe?)
    @op
    def run(self) -> Any:
        # TODO: Nicer result type
        import litellm

        result = litellm.completion(
            messages=list(self),
            model=self.config.get("model", "gpt-4o-mini"),
        )
        # TODO: Print in a nicer format
        return result
