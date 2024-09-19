import copy
import inspect
import json
import os
import re
import textwrap
from collections import UserDict, UserList
from collections.abc import Mapping
from pathlib import Path
from typing import IO, Any, Optional, TypedDict, Union

from pydantic import Field
from rich.table import Table

from weave.flow.obj import Object
from weave.flow.prompt.common import Role, color_role
from weave.trace.rich import pydantic_util
from weave.trace.api import attributes as weave_attributes
from weave.trace.api import publish as weave_publish
from weave.trace.refs import ObjectRef


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
    for role in Role:
        prefix = role.value + ":"
        if content.startswith(prefix):
            return {
                "role": role.value,
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


# class PromptResult(litellm.types.utils.ModelResponse):
#     def __init__(
#         self, prompt: "Prompt", response: litellm.types.utils.ModelResponse
#     ) -> None:
#         super().__init__(**response.model_dump())
#         self.prompt = prompt

#     @property
#     def history(self) -> Table:
#         """Show prompt messages as well as the response."""
#         table = Table(title="Conversation", title_justify="left", show_header=False)
#         table.add_column("Role", justify="right")
#         table.add_column("Content")
#         # TODO: Maybe we should inline the values here? Or highlight placeholders missing values in red?
#         for message in self.prompt:
#             table.add_row(
#                 color_role(message.get("role", "user")),
#                 color_content(message.get("content", ""), self.prompt._values),
#             )
#         for choice in self.choices:
#             table.add_row(color_role(choice.message.role), choice.message.content)
#         return table

#     def messages_table(self, title: Optional[str] = None) -> Table:
#         table = Table(show_header=False)
#         table.add_column("Role", justify="right")
#         table.add_column("Content")
#         for choice in self.choices:
#             table.add_row(color_role(choice.message.role), choice.message.content)
#         return table

#     def print(self) -> str:
#         tables = []
#         tables.append(self.messages_table(title="Choices"))
#         tables = [pydantic_util.table_to_str(t) for t in tables]
#         return "\n".join(tables)

#     def _repr_pretty_(self, p: Any, cycle: bool) -> None:
#         """Show a nicely formatted table in ipython."""
#         if cycle:
#             p.text("Prompt(...)")
#         else:
#             p.text(self.print())

#     def __iadd__(self, other: Any) -> "Prompt":
#         return self.append(other)

#     def append(
#         self,
#         other: Any,
#         role: Optional[str] = None,
#         dedent: bool = False,
#     ) -> "Prompt":
#         new_prompt = self.prompt.copy()
#         new_prompt.append(self.choices[0].message)
#         return new_prompt.append(other, role, dedent)


class Prompt(UserList, Object, Mapping):
    data: list = Field(default_factory=list)
    config: dict = Field(default_factory=dict)
    requirements: dict = Field(default_factory=dict)

    _values: dict

    def __init__(
        self,
        content: Optional[str | dict | list] = None,
        *,
        role: Optional[str] = None,
        dedent: bool = False,
        **kwargs: Any,
    ) -> None:
        super(UserList, self).__init__()
        if "messages" in kwargs:
            content = kwargs.pop("messages")
            kwargs = {"config": kwargs}
        super(Object, self).__init__(**kwargs)
        # super(UserDict, self).__init__()
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
        other: Any,
        role: Optional[str] = None,
        dedent: bool = False,
    ) -> "Prompt":
        if isinstance(other, str):
            # Seems like we don't want to do this, if the user wants
            # all system we have helpers for that, and we want to make the
            # case of constructing system + user easy
            # role = self.data[-1].get("role", "user") if self.data else "user"
            self.data.append(str_to_message(other, role=role, dedent=dedent))
        elif isinstance(other, dict):
            # TODO: Validate that other has message shape
            # TODO: Override role and do dedent?
            self.data.append(other)
        elif isinstance(other, list):
            for item in other:
                self.append(item)
        else:
            raise ValueError(f"Cannot append {other} of type {type(other)} to Prompt")
        return self

    def __iadd__(self, other: Any) -> "Prompt":
        return self.append(other)

    def copy(self) -> "Prompt":
        """Create a deep copy of the Prompt object."""
        new_prompt = Prompt()
        new_prompt.name = self.name
        new_prompt.description = self.description
        new_prompt.data = copy.deepcopy(self.data)
        new_prompt.config = copy.deepcopy(self.config)
        new_prompt._values = copy.deepcopy(self._values)
        new_prompt.requirements = copy.deepcopy(self.requirements)
        return new_prompt

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
        all_placeholders = []
        for message in self.data:
            # TODO: Support placeholders in image messages?
            placeholders = extract_placeholders(message["content"])
            all_placeholders.extend(p for p in placeholders if p not in all_placeholders)
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

    def bind(self, *args, **kwargs: Any) -> "Prompt":
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

    def __call__(self, *args: Any, **kwargs: Any) -> "Prompt":
        if len(args) == 1 and len(kwargs) == 0 and isinstance(args[0], dict):
            kwargs = args[0]
        return self.bind(kwargs)

    # TODO: Any should be Dataset but there is a circular dependency issue
    def bind_rows(self, dataset: Union[list[dict], Any]) -> list["Prompt"]:
        rows = dataset if isinstance(dataset, list) else dataset.rows
        bound: list["Prompt"] = []
        for row in rows:
            bound.append(self.copy().bind(row))
        return bound

    def __getitem__(self, key: Union[int, slice]) -> Union[Message, "Prompt"]:
        """Override getitem to return a Message or a new Prompt object."""
        # print('__getitem__ called', key, type(key))
        if isinstance(key, int):
            message = self.data[key].copy()
            placeholders = extract_placeholders(message["content"])
            values = {}
            for placeholder in placeholders:
                if placeholder in self._values:
                    values[placeholder] = self._values[placeholder]
                elif placeholder in self.requirements and 'default' in self.requirements[placeholder]:
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
            if key == 'ref':
                return self
            if key == 'messages':
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

    # def run(self, model: Optional[str] = None, **kwargs: Any) -> Any:
    #     call_kwargs = {
    #         "model": "gpt-3.5-turbo",
    #     }
    #     call_kwargs.update(self.config)
    #     if model:
    #         call_kwargs["model"] = model
    #     call_kwargs.update(kwargs)
    #     with weave_attributes({"weave": {"prompt_values": self._values}}):
    #         result = litellm.completion(messages=self, **call_kwargs)
    #     return PromptResult(self, result)

    def publish(self, name: Optional[str] = None) -> ObjectRef:
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

    def __iter__(self):
        # print('__iter__ called')
        current_frame = inspect.currentframe()
        caller_frame = current_frame.f_back
        caller_info = inspect.getframeinfo(caller_frame)
        if caller_info.function == '__iter__':
            # print('unpacking!')
            yield 'ref'
            yield 'messages'
            for key in self.config:
                yield key
        else:
            for i in range(len(self)):
                m = self.__getitem__(i)
                yield m


    def as_dict(self) -> dict[str, Any]:
        return dict(self)

    @staticmethod
    def from_obj(obj: Any) -> "Prompt":
        return Prompt(
            name=obj.name,
            description=obj.description,
            messages=obj.messages,
            config=obj.config,
            requirements=obj.requirements,
        )

    @staticmethod
    def load(fp: IO) -> "Prompt":
        if isinstance(fp, str):  # Common mistake
            raise ValueError(
                "Prompt.load() takes a file-like object, not a string. Did you mean Prompt.load_file()?"
            )
        data = json.load(fp)
        prompt = Prompt()
        # prompt.name = data.get("name")
        # prompt.description = data.get("description")
        # for message_data in data.get("messages", []):
        #     prompt.append(Message(**message_data))
        return prompt

    @staticmethod
    def load_file(filepath: Union[str, Path]) -> "Prompt":
        expanded_path = os.path.expanduser(str(filepath))
        with open(expanded_path, "r") as f:
            return Prompt.load(f)

    def dump(self, fp: IO) -> None:
        json.dump(self.as_dict(), fp, indent=2)

    def dump_file(self, filepath: Union[str, Path]) -> None:
        expanded_path = os.path.expanduser(str(filepath))
        with open(expanded_path, "w") as f:
            self.dump(f)

    # def __getitem__(self, key: Union[int, slice, str]) -> Any:
    #     print(f"__getitem__ called with key: {key}")
    #     if isinstance(key, (int, slice)):
    #         return super(UserList, self).__getitem__(key)
    #     return super(UserDict, self).__getitem__(key)

    # def __setitem__(self, key: Union[int, str], value: Any) -> None:
    #     print(f"__setitem__ called with key: {key}, value: {value}")
    #     if isinstance(key, int):
    #         super(UserList, self).__setitem__(key, value)
    #     else:
    #         super(UserDict, self).__setitem__(key, value)

    # def __delitem__(self, key: Union[int, str]) -> None:
    #     print(f"__delitem__ called with key: {key}")
    #     if isinstance(key, int):
    #         super(UserList, self).__delitem__(key)
    #     else:
    #         super(UserDict, self).__delitem__(key)

    # def __contains__(self, key: Any) -> bool:
    #     print(f"__contains__ called with key: {key}")
    #     return super(UserDict, self).__contains__(key)

    # def __len__(self) -> int:
    #     print("__len__ called")
    #     return super(UserList, self).__len__()

    # def __iter__(self):
    #     print("__iter__ called")
    #     return super(UserList, self).__iter__()

    # def keys(self) -> KeysView:
    #     return self.config.keys()
    #     # print("keys called")
    #     # return super(UserDict, self).keys()

    # def values(self) -> ValuesView:
    #     print("values called")
    #     return super(UserDict, self).values()

    # def items(self):
    #     print("items called")
    #     return super(UserDict, self).items()

    # def get(self, key: Any, default: Any = None) -> Any:
    #     print(f"get called with key: {key}, default: {default}")
    #     return super(UserDict, self).get(key, default)

    # def clear(self) -> None:
    #     print("clear called")
    #     super(UserDict, self).clear()

    # def update(self, *args: Any, **kwargs: Any) -> None:
    #     print(f"update called with args: {args}, kwargs: {kwargs}")
    #     super(UserDict, self).update(*args, **kwargs)

    # def pop(self, key: Any, default: Any = None) -> Any:
    #     print(f"pop called with key: {key}, default: {default}")
    #     return super(UserDict, self).pop(key, default)

    # def popitem(self) -> Tuple[Any, Any]:
    #     print("popitem called")
    #     return super(UserDict, self).popitem()

    # def setdefault(self, key: Any, default: Any = None) -> Any:
    #     print(f"setdefault called with key: {key}, default: {default}")
    #     return super(UserDict, self).setdefault(key, default)
