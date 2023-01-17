import json

from .. import weave_types as types
from ..api import op, weave_class
from .. import artifact_local
from .. import artifact_wandb
from .. import uris


class LocalArtifactVersionType(types.Type):
    instance_classes = artifact_local.LocalArtifact
    instance_class = artifact_local.LocalArtifact

    def instance_to_dict(self, obj):
        return {
            "uri": obj.uri(),
        }

    def instance_from_dict(self, d):

        uri = uris.WeaveLocalArtifactURI(d["uri"])
        return artifact_local.LocalArtifact(uri._full_name, uri._version)


class WandbArtifactVersionType(types.Type):
    instance_classes = artifact_wandb.WandbArtifact
    instance_class = artifact_wandb.WandbArtifact

    def instance_to_dict(self, obj):
        return {
            "uri": obj.uri(),
        }

    def instance_from_dict(self, d):
        uri = uris.WeaveWBArtifactURI(d["uri"])
        return artifact_local.WandbArtifact(uri._full_name, uri=uri)
