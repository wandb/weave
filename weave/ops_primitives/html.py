import dataclasses

from .. import weave_types as types
from .. import api as weave


class HtmlType(types.Type):
    def save_instance(self, obj, artifact, name):
        with artifact.new_file(f"{name}.html") as f:
            f.write(obj.html)

    def load_instance(self, artifact, name, extra=None):
        with artifact.open(f"{name}.html") as f:
            return Html(f.read())


@weave.weave_class(weave_type=HtmlType)
@dataclasses.dataclass
class Html:
    html: str


HtmlType.instance_classes = Html
