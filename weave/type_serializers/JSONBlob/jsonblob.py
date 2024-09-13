import json
from typing import Any

from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact


class JSONBlob:
    def __init__(self, obj: Any, size: int) -> None:
        self.obj = obj
        self.size = size

    def __repr__(self) -> str:
        return f"JSONBlob <{self.size} bytes>"


def save(obj: JSONBlob, artifact: MemTraceFilesArtifact, name: str) -> None:
    with artifact.new_file("blob.json", binary=False) as f:
        json.dump(obj.obj, f)


def load(artifact: MemTraceFilesArtifact, name: str) -> JSONBlob:
    with artifact.path("blob.json") as f:
        return JSONBlob(json.load(f))


def register() -> None:
    serializer.register_serializer(JSONBlob, save, load)
