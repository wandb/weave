import json

from .. import weave_types as types
from .. import storage
from .. import tags
from ..api import op, weave_class
from ..ops_domain import image


class LocalArtifactType(types.ObjectType):
    name = "local-artifact"

    def property_types(self):
        return {"name": types.String(), "version": types.String()}


@weave_class(weave_type=LocalArtifactType)
class LocalArtifact:
    def __init__(self, name, version):
        self.name = name
        self.version = version

    @op(
        name="localArtifact-get",
        input_type={"self": LocalArtifactType(), "path": types.String()},
        output_type=image.WBImageType(),
    )
    def get(self, path):
        # TODO: why are we ignoring name? Because we're relying on default _obj
        # name probably?
        return storage.get_version(self.name, self.version)

        # Options, mixin, associate, hard-code
        # I think associate is nice and easy...


LocalArtifactType.instance_classes = LocalArtifact
LocalArtifactType.instance_class = LocalArtifact


@op(
    name="root-localArtifact",
    input_type={"name": types.String(), "version": types.String()},
    output_type=LocalArtifactType(),
)
def local_artifact(name, version):
    return LocalArtifact(name, version)
