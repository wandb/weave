import dataclasses
import typing
from .. import types
from .. import api as weave

# Artifact entries implement a File interface.


# A file versioned by an artifact, either inside or a bucket Ref
class ArtifactEntryType(types.Type):
    def save_instance(self, obj, artifact, name):
        # No-op, this is already a saved ArtifactEntry!
        pass

    def load_instance(self, artifact, name, extra=None):
        return ArtifactEntry(artifact, name)


@dataclasses.dataclass
class ArtifactEntry:
    artifact: typing.Any  # Artifact
    path: str


ArtifactEntryType.instance_classes = ArtifactEntry
ArtifactEntryType.instance_class = ArtifactEntry


@weave.type(__override_name="image-file")  # type: ignore
class ImageArtifactEntry:
    # TODO: just File? No, because the frontend is going to call .artifactVersion()
    #     on us. So we need to be ImageArtifactEntry
    path: ArtifactEntry  # This should be a Ref<File<ImageExtensions>>
    format: str
    height: int
    width: int
    sha256: str

    @property
    def artifact(self):
        return self.path.artifact


class HtmlType(types.Type):
    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.html") as f:
            f.write(obj.html)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.pt", binary=True) as f:
            return f.read()


@weave.weave_class(weave_type=HtmlType)
@dataclasses.dataclass
class Html:
    html: str


HtmlType.instance_classes = Html


@weave.type(__override_name="html-file")  # type: ignore
class HtmlFile:
    path: ArtifactEntry  # This should be a Ref<File<ImageExtensions>>


@weave.op()
def html_file(html: Html) -> HtmlFile:
    from weave import storage

    ref = storage.save(html)
    return HtmlFile(ref)
    # return HtmlFile(ArtifactEntry(ref.artifact, ref.name))
