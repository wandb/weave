# Implements backward compatibilty for existin W&B Media types.

import copy
import dataclasses
import typing
from .. import types
from .. import api as weave
from ..ops_primitives import html


## This is an ArtifactRefii, that lets us get access to the ref
# artifact/path during loading.


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
class ImageArtifactFileRef:
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


@weave.type(__override_name="html-file")  # type: ignore
class HtmlArtifactFileRef:
    path: ArtifactEntry


# This shows a pattern for how to convert an in memory object (Html)
# to a W&B media type style FileRef, so that the existing frontend
# code can work with it.
@weave.op()
def html_file(html: html.Html) -> HtmlArtifactFileRef:
    from weave import storage

    # This is a ref to the html object
    ref = storage.save(html)
    ref = copy.copy(ref)
    ref.path += ".html"
    return HtmlArtifactFileRef(ref)
