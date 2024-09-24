import json
from typing import Any

from weave.flow.obj import Object
from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact


class JSONBlob(Object):
    obj: Any
    size: int

    def __repr__(self) -> str:
        return f"JSONBlob <{self.size} bytes>"


def save(obj: JSONBlob, artifact: MemTraceFilesArtifact, name: str) -> None:
    with artifact.new_file("blob.json", binary=False) as f:
        json.dump(obj.obj, f)  # type: ignore


def load(artifact: MemTraceFilesArtifact, name: str) -> JSONBlob:
    path = artifact.path("blob.json")
    with open(path, "r") as f:
        data = f.read()
        return JSONBlob(obj=json.loads(data), size=len(data))


def register() -> None:
    serializer.register_serializer(JSONBlob, save, load)
