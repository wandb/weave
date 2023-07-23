from dataclasses import dataclass, field
import typing
import json
from . import stitch


@dataclass
class InputProvider:
    raw: dict[str, typing.Any]
    _dumps_cache: dict[str, str] = field(init=False, repr=False, default_factory=dict)

    def __getitem__(self, key: str) -> typing.Any:
        if key not in self.raw:
            raise KeyError(f"Input {key} not found")
        if key not in self._dumps_cache:
            self._dumps_cache[key] = json.dumps(
                self.raw[key] if self.raw[key] != None else ""
            )
        return self._dumps_cache[key]


@dataclass
class InputAndStitchProvider(InputProvider):
    stitched_obj: stitch.ObjectRecorder
