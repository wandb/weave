import faiss
import weave


class FaissIndexType(weave.types.Type):
    instance_classes = [faiss.Index]

    def save_instance(self, obj, artifact, name):
        with artifact.writeable_file_path(f"{name}.faissindex") as write_path:
            faiss.write_index(obj, write_path)

    def load_instance(self, artifact, name, extra):
        return faiss.read_index(artifact.path(f"{name}.faissindex"))
