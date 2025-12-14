from typing import Optional

from weave.trace_server.interface.builtin_object_classes import base_object_def


class Mod(base_object_def.BaseObject):
    secrets: list[str]
    classifiers: list[str]
    entrypoint: list[str]
    version: str
    env: dict[str, str]
    image: str
    repository: Optional[str]

__all__ = ["Mod"]
