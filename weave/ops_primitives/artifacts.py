import json

from .. import weave_types as types
from ..api import op, weave_class
from .. import artifacts_local
from .. import uris


class LocalArtifactVersionType(types.Type):
    instance_classes = artifacts_local.LocalArtifact
    instance_class = artifacts_local.LocalArtifact

    def instance_to_dict(self, obj):
        return {
            "uri": obj.uri(),
        }

    def instance_from_dict(self, d):

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
        uri = uris.WeaveWBArtifactURI(d["uri"])
        return artifacts_local.WandbArtifact(uri._full_name, uri=uri)
