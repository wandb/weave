from .. import panel
from .. import weave_types as types
from ..api import op, weave_class


class SizedString(panel.Panel):
    def __init__(self, input_node):
        self.id = "sized-string"
        self.input_node = input_node
        self.config = SizedStringConfig("small")


class SizedStringConfigType(types.ObjectType):
    name = "sized_string_config"

    def __init__(self):
        pass

    def property_types(self):
        return {
            "size": types.String(),
        }


@weave_class(weave_type=SizedStringConfigType)
class SizedStringConfig(object):
    def __init__(self, size):
        self.size = size

    @op(
        name="sizedstringconfig-setsize",
        input_type={"conf": SizedStringConfigType(), "size": types.String()},
        output_type=types.TypeType(),
    )
    def set_size(conf, size):
        conf.size = size
        return conf

    def _set_size(self, size):
        self.size = size


SizedStringConfigType.instance_classes = SizedStringConfig
SizedStringConfigType.instance_class = SizedStringConfig
