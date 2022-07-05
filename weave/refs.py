from collections.abc import Iterable
import copy
import typing
import os
import json

from . import artifacts_local
from . import weave_types as types
from . import errors
from . import box
from . import artifacts_local
from . import uris
from . import graph


class Ref:
    extra: list[str]

    def _ipython_display_(self):
        from . import show

        return show(self)

    @property
    def is_saved(self):
        return self.artifact.is_saved

    # TODO: This local ref stuff should be split out to separate class.
    # Its a hack.
    @classmethod
    def from_local_ref(cls, artifact, s, type):
        path, extra = cls.parse_local_ref_str(s)
        if isinstance(artifact, artifacts_local.LocalArtifact):
            return LocalArtifactRef(artifact, path=path, extra=extra, type=type)
        elif isinstance(artifact, artifacts_local.WandbArtifact):
            return WandbArtifactRef(artifact, path=path, extra=extra, type=type)

    @classmethod
    def parse_local_ref_str(cls, s):
        if "#" not in s:
            return s, None
        path, extra = s.split("#", 1)
        return path, extra.split("/")

    @property
    def name(self) -> str:
        raise NotImplementedError()

    @property
    def uri(self) -> str:
        raise NotImplementedError()

    def get(self):
        raise NotImplementedError()

    def __str__(self) -> str:
        return self.uri


# We store REFS here if we can't attach them directly to the object
REFS: dict[str, typing.Any] = {}


def get_ref(obj):
    if hasattr(obj, "_ref"):
        return obj._ref
    try:
        if id(obj) in REFS:
            return REFS[id(obj)]
    except TypeError:
        pass
    return None


def put_ref(obj, ref):
    try:
        obj._ref = ref
    except AttributeError:
        if isinstance(obj, (int, float, str, list, dict, set)):
            return
        REFS[id(obj)] = ref


def clear_ref(obj):
    try:
        delattr(obj, "_ref")
    except AttributeError:
        pass
    if id(obj) in REFS:
        REFS.pop(id(obj))


class WandbArtifactRef(Ref):
    artifact: "artifacts_local.WandbArtifact"

    def __init__(self, artifact, path, type=None, obj=None, extra=None):
        self.artifact = artifact
        self.path = path
        self._type = type
        self.obj = obj
        self.extra = extra

    @property
    def version(self):
        return self.artifact.version

    @property
    def type(self):
        if self._type is not None:
            return self._type
        if self.path is None:
            # If there's no path, this is a Ref directly to an ArtifactVersion
            # TODO: refactor
            from .ops_domain import wbartifact

            return wbartifact.ArtifactVersionType()
        try:
            with self.artifact.open(f"{self.path}.type.json") as f:
                type_json = json.load(f)
        except (FileNotFoundError, KeyError):
            # If there's no type file, this is a Ref to the file itself
            # TODO: refactor
            from .ops_domain import file_wbartifact

            return file_wbartifact.ArtifactVersionFileType()
        self._type = types.TypeRegistry.type_from_dict(type_json)
        return self._type

    @property
    def name(self) -> str:
        return self.artifact.location.full_name

    @property
    def uri(self) -> str:
        # TODO: should artifacts themselves be "extras" aware??
        # this is really clunky but we cannot use artifact URI since we need
        # to handle extras here which is not present in the artifact
        uri = uris.WeaveURI.parse(self.artifact.uri())
        uri.extra = self.extra
        uri.file = self.path
        return uri.uri

    def versions(self):
        # TODO: implement versions on wandb artifact
        return [self.artifact.version]

    def get(self):
        if self.obj is not None:
            return self.obj
        if self.path is None:
            return self.artifact
        obj = self.type.load_instance(self.artifact, self.path, extra=None)
        obj = box.box(obj)
        put_ref(obj, self)
        self.obj = obj
        return obj

    @classmethod
    def from_str(cls, s):
        uri = uris.WeaveWBArtifactURI(s)
        # TODO: potentially need to pass full entity/project/name instead
        return cls(
            artifacts_local.WandbArtifact(uri.full_name, uri=uri),
            path=uri.file,
        )


types.WandbArtifactRefType.instance_class = WandbArtifactRef
types.WandbArtifactRefType.instance_classes = WandbArtifactRef


class LocalArtifactRef(Ref):
    artifact: "artifacts_local.LocalArtifact"

    def __init__(self, artifact, path, type=None, obj=None, extra=None):
        self.artifact = artifact
        self.path = path
        if "/" in self.path:
            raise errors.WeaveInternalError(
                '"/" in path not yet supported: %s' % self.path
            )
        if self.path is None:
            raise errors.WeaveInternalError("path must not be None")
        self._type = type
        self.obj = obj
        self.extra = extra
        if obj is not None:
            obj = box.box(obj)
            put_ref(obj, self)

    @property
    def uri(self) -> str:
        # TODO: should artifacts themselves be "extras" aware??
        # this is really clunky but we cannot use artifact URI since we need
        # to handle extras here which is not present in the artifact
        uri = uris.WeaveURI.parse(self.artifact.uri())
        uri.extra = self.extra
        uri.file = self.path
        return uri.uri

    @property
    def version(self):
        return self.artifact.version

    @property
    def type(self):
        if self._type is not None:
            return self._type
        # if self.path != "_obj":
        #     raise errors.WeaveInternalError(
        #         "Trying to load type from a non-root object. Ref should be instantiated with a type for this object: %s %s"
        #         % (self.artifact, self.path)
        #     )
        with self.artifact.open(f"{self.path}.type.json") as f:
            type_json = json.load(f)
        self._type = types.TypeRegistry.type_from_dict(type_json)
        return self._type

    @property
    def name(self) -> str:
        return self.artifact.location.full_name

    def get(self) -> typing.Any:
        # Can't do this, when you save a list, you get a different
        # representation back which test_decorators.py depend on right now
        if self.obj is not None:
            return self.obj
        obj = self.type.load_instance(self.artifact, self.path, extra=self.extra)
        obj = box.box(obj)
        put_ref(obj, self)
        self.obj = obj
        return obj

    def versions(self):
        artifact_path = os.path.join(
            artifacts_local.local_artifact_dir(), self.artifact._name
        )
        versions = []
        for version_name in os.listdir(artifact_path):
            if (
                not os.path.islink(os.path.join(artifact_path, version_name))
                and not version_name.startswith("working")
                and not version_name.startswith(".")
            ):
                # This is ass-backward, have to get the full object to just
                # get the ref.
                # TODO
                art = self.artifact.get_other_version(version_name)
                ref = LocalArtifactRef(art, path="_obj")
                # obj = uri.get()
                # ref = get_ref(obj)
                versions.append(ref)
        return sorted(versions, key=lambda v: v.artifact.created_at)

    @classmethod
    def from_str(cls, s, type=None):
        loc = uris.WeaveLocalArtifactURI(s)
        return cls(
            artifacts_local.LocalArtifact(loc.full_name, loc.version),
            path=loc.file,
            type=type,
            obj=None,
            extra=loc.extra,
        )

    def local_ref_str(self):
        s = self.path
        if self.extra is not None:
            s += "#%s" % "/".join(self.extra)
        return s


types.LocalArtifactRefType.instance_class = LocalArtifactRef
types.LocalArtifactRefType.instance_classes = LocalArtifactRef


def node_to_ref(node: graph.Node) -> typing.Optional[Ref]:
    """Converts a Node to equivalent Ref if possible.

    Specific call sequences can be converted to refs. For example:
      get(<object_path>)[0]['a'] can be converted to a Ref.

    The rule is:
      - a get call can be converted to a Ref
      - any __getitem__ (or pick) call can be converted to a Ref if its input is a Node
        that can be converted to a Ref

    Its desirable to store these as Refs rather than nodes because:
      - The representation is much more compact
      - A ref is a guarantee of existence
      - Artifacts is aware of cross-artifact references and keeps them
        consistent (it does not allow deletion an artifact that has exisiting
          depending artifacts)

    This is used when saving objects, to achieve cross-artifact references.

    A user may compose objects from values fetched from other objects. For example:
    x = weave.save({'a': 5})
    y = weave.save({'b': x['a']})

    Since Weave is lazy, x['a'] produces a Node. When we save objects, if a Node
      is encountered we try to convert it to a Ref using this function. If that
      succeeds, we save in Ref format instead of Node format.

    # TODO: we need to tell the artifact this Ref exists, so that it creates
    #   the database dependency, which is how we achieve consistency.
    """
    nodes = graph.linearize(node)
    if nodes is None:
        return None

    # First node in chain must be get op
    # TODO: check its a get of a specific artifact version, not an alias!
    #     maybe we should have two different ops for that, so we can distinguish
    #     via type instead of via string checking.
    if nodes[0].from_op.name != "get":
        return None
    get_arg0 = list(nodes[0].from_op.inputs.values())[0]
    if not isinstance(get_arg0, graph.ConstNode):
        return None
    uri = get_arg0.val
    parsed_uri = uris.WeaveURI.parse(uri)
    ref = parsed_uri.to_ref()
    if ref.extra is None:
        ref.extra = []

    # Remaining nodes in chain must be __getitem__
    for node in nodes[1:]:
        if not (
            node.from_op.name.endswith("__getitem__")
            # Allow pick too, but this is kinda busted. What if both exist?
            # I think we should maybe just use __getitem__ to implement both
            # of these. If passed a string, its a column lookup, int is row
            # lookup. Some other tools do this. However, if that's the solution,
            # then our "ref extra is list of string" solution doesn't work.
            # TODO: fix
            or node.from_op.name.endswith("pick")
        ):
            return None
        getitem_arg1 = list(node.from_op.inputs.values())[1]
        if not isinstance(getitem_arg1, graph.ConstNode):
            return None
        ref.extra.append(str(getitem_arg1.val))
    return ref


def ref_to_node(ref: Ref) -> typing.Optional[graph.Node]:
    """Inverse of node_to_ref, see docstring for node_to_ref."""
    from .ops_primitives.weave_api import get as op_get

    if ref.extra is None:
        return None
    extra = ref.extra
    ref = copy.copy(ref)
    ref.extra = []

    node = op_get(str(ref))
    for str_key in extra:
        key: typing.Union[str, int] = str_key
        try:
            key = int(str_key)
        except ValueError:
            pass
        if hasattr(node, "__getitem__"):
            node = node[key]
        elif hasattr(node, "pick"):
            node = node.pick(key)
        else:
            return None
    return node
