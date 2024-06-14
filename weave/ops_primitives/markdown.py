import dataclasses

from weave import api as weave
from weave import weave_types as types


class MarkdownType(types.Type):
    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.md") as f:
            f.write(obj.md)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.md") as f:
            return Markdown(f.read())


@weave.weave_class(weave_type=MarkdownType)
@dataclasses.dataclass
class Markdown:
    md: str


MarkdownType.instance_classes = Markdown
