import json

from .. import weave_types as types
from .. import storage
from .. import tags
from ..api import op, weave_class
from .. import artifacts_local


class LocalArtifactVersionType(types.Type):
    instance_classes = artifacts_local.LocalArtifact
    instance_class = artifacts_local.LocalArtifact

    def instance_to_dict(self, obj):
        return {
            "uri": obj.uri(),
        }

    def instance_from_dict(self, d):
        from .. import uris

        uri = uris.WeaveLocalArtifactURI(d["uri"])
        return artifacts_local.LocalArtifact(uri._full_name, uri._version)


class WandbArtifactVersionType(types.Type):
    instance_classes = artifacts_local.WandbArtifact
    instance_class = artifacts_local.WandbArtifact

    def instance_to_dict(self, obj):
        return {
            "uri": obj.uri(),
        }

    def instance_from_dict(self, d):
        from .. import uris

        uri = uris.WeaveWBArtifactURI(d["uri"])
        return artifacts_local.WandbArtifact(uri._full_name, uri=uri)
