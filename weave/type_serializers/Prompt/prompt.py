"""Defines the custom Messages weave type."""

from weave.flow.prompt import Messages
from weave.trace import serializer
from weave.trace.custom_objs import MemTraceFilesArtifact


def save(obj: "Messages", artifact: MemTraceFilesArtifact, name: str) -> None:
    # See discussion on image serializer for why name is ignored.
    with artifact.new_file("obj.json") as f:
        obj.dump(f)


def load(artifact: MemTraceFilesArtifact, name: str) -> "Messages":
    # Note: I am purposely ignoring the `name` here and hard-coding the filename. See comment
    # on save.
    path = artifact.path("obj.json")
    with open(path, "r") as fp:
        return Messages.load(fp)


def register() -> None:
    serializer.register_serializer(Messages, save, load)
