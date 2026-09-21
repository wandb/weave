"""Passive object-reference data and validation, without SDK dereferencing."""

from __future__ import annotations

from concurrent.futures import Future
from dataclasses import dataclass

from weave.shared import refs_internal


@dataclass(frozen=True)
class ObjectRef:
    entity: str
    project: str
    name: str
    _digest: str | Future[str]
    _extra: tuple[str | Future[str], ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self._digest, str):
            refs_internal.validate_no_slashes(self._digest, "digest")
            refs_internal.validate_no_colons(self._digest, "digest")

        refs_internal.validate_no_slashes(self.name, "name")
        refs_internal.validate_no_colons(self.name, "name")
