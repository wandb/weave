"""Weave plugin for mypy.

@weave.type() is a decorator that behaves like Python's @dataclasess.dataclass().
This tells mypy to treat it as such.
"""

from typing import Callable, Optional

from mypy.plugin import ClassDefContext, Plugin


class WeavePlugin(Plugin):
    def get_class_decorator_hook(
        self, fullname: str
    ) -> Optional[Callable[[ClassDefContext], None]]:
        from mypy.plugins import dataclasses

        if fullname in ["weave.decorator_type.type"]:
            return dataclasses.dataclass_tag_callback
        return None

    def get_class_decorator_hook_2(
        self, fullname: str
    ) -> Optional[Callable[[ClassDefContext], bool]]:
        from mypy.plugins import dataclasses

        if fullname in ["weave.decorator_type.type"]:
            return dataclasses.dataclass_class_maker_callback
        return None


def plugin(version: str):
    # ignore version argument if the plugin works with all mypy versions.
    return WeavePlugin
