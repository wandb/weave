import faiss
import typing
import weave

from weave import artifact_fs


class FaissIndexType(weave.types.Type):
    instance_classes = [faiss.Index]

    def save_instance(
        self, obj: faiss.Index, artifact: artifact_fs.FilesystemArtifact, name: str
    ) -> None:
        with artifact.writeable_file_path(f"{name}.faissindex") as write_path:
            faiss.write_index(obj, write_path)

    def load_instance(
        self,
        artifact: artifact_fs.FilesystemArtifact,
        name: str,
        extra: typing.Optional[list[str]] = None,
    ) -> faiss.Index:
        return faiss.read_index(artifact.path(f"{name}.faissindex"))
