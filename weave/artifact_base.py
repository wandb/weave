import contextlib
import typing

from . import ref_util

if typing.TYPE_CHECKING:
    from . import ref_artifact
    from . import weave_types as types


class Artifact:
    RefClass: typing.ClassVar[typing.Type["ref_artifact.ArtifactRef"]]
    name: str

    @property
    def is_saved(self) -> bool:
        raise NotImplementedError

    @contextlib.contextmanager
    def open(self, path: str, binary: bool = False):
        raise NotImplementedError

    @contextlib.contextmanager
    def new_file(self, path: str, binary: bool = False):
        raise NotImplementedError

    def ref_from_local_str(
        self, s: str, type: "types.Type"
    ) -> "ref_artifact.ArtifactRef":
        path, extra = ref_util.parse_local_ref_str(s)
        return self.RefClass(self, path=path, extra=extra, type=type)

    @property
    def created_at(self):
        raise NotImplementedError

    @property
    def version(self):
        raise NotImplementedError

    @property
    def location(self):
        raise NotImplementedError
