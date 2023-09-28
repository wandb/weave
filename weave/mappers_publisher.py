import typing
from weave import box, graph
from weave.artifact_wandb import likely_commit_hash
from weave.language_features.tagging import tag_store
from weave.node_ref import ref_to_node
from weave.uris import WeaveURI
from . import mappers
from . import ref_base
from . import weave_types as types
from . import errors
from . import mappers_python_def
from .language_features.tagging import tagged_value_type
import dataclasses
from weave import weave_internal, context, storage
from .ops_primitives import weave_api


class RefToPyRef(mappers.Mapper):
    def apply(self, obj: ref_base.Ref):
        if _uri_is_local_artifact(obj.uri):
            obj = _local_ref_to_published_ref(obj)

        return obj


class FunctionToPyFunction(mappers.Mapper):
    def __init__(self, type_, mapper, artifact_, path):
        super().__init__(type_, mapper, artifact_, path)
        self.artifact = artifact_

    def apply(self, obj):
        res = graph.map_nodes_full([obj], _node_publish_mapper)[0]

        # Find any op gets and add cross-artifact dependencies.
        # We want to do this after we have recursively published any
        # local artifacts above.
        def _node_dep_mapper(node: graph.Node) -> graph.Node:
            if _node_is_op_get(node):
                node = typing.cast(graph.OutputNode, node)
                uri = _uri_of_get_node(node)
                self.artifact.add_artifact_reference(uri)
            return node

        graph.map_nodes_full([res], _node_dep_mapper)
        return res


class ObjectToPyDict(mappers_python_def.ObjectToPyDict):
    def apply(self, obj):
        try:
            res = super().apply(obj)
            copy_obj = dataclasses.copy.copy(obj)
            for prop_name, prop_serializer in self._property_serializers.items():
                if prop_serializer is not None:
                    setattr(copy_obj, prop_name, res[prop_name])
            obj = copy_obj
        except Exception as e:
            print(e)
            pass
        return obj


class UnionToPyUnion(mappers_python_def.UnionToPyUnion):
    def apply(self, obj):
        res = super().apply(obj)
        if not isinstance(res, dict):
            raise errors.WeaveSerializeError("")
        if isinstance(obj, dict):
            return {k: v for k, v in res.items() if k != "_union_id"}
        else:
            return res["_val"]


class TaggedValueToPy(tagged_value_type.TaggedValueToPy):
    def apply(self, obj: typing.Any) -> dict:
        res = super().apply(obj)
        value = self._value_serializer.apply(res["_value"])
        tags = self._tag_serializer.apply(res["_tag"])
        value = box.box(value)
        tag_store.add_tags(value, tags)
        return value


def map_to_python_remote_(type, mapper, artifact, path=[], mapper_options=None):
    if isinstance(type, types.Function):
        return FunctionToPyFunction(type, mapper, artifact, path)
    elif isinstance(type, types.RefType):
        return RefToPyRef(type, mapper, artifact, path)

    elif isinstance(type, types.TypedDict):
        return mappers_python_def.TypedDictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, types.Dict):
        return mappers_python_def.DictToPyDict(type, mapper, artifact, path)
    elif isinstance(type, types.List):
        return mappers_python_def.ListToPyList(type, mapper, artifact, path)
    elif isinstance(type, types.UnionType):
        return UnionToPyUnion(type, mapper, artifact, path)
    elif isinstance(type, types.ObjectType):
        return ObjectToPyDict(type, mapper, artifact, path)
    elif isinstance(type, tagged_value_type.TaggedValueType):
        return TaggedValueToPy(type, mapper, artifact, path)
    elif isinstance(type, types.Const):
        return mappers_python_def.ConstToPyConst(type, mapper, artifact, path)

    return mappers.Mapper(type, mapper, artifact, path)


map_to_python_remote = mappers.make_mapper(map_to_python_remote_)


def _node_publish_mapper(node: graph.Node) -> typing.Optional[graph.Node]:
    if _node_is_op_get(node):
        node = typing.cast(graph.OutputNode, node)
        uri = _uri_of_get_node(node)
        if uri is not None and _uri_is_local_artifact(uri):
            # Be sure to merge the node if needed before continuing with the publish.
            if weave_api.get_merge_spec_uri(uri):
                return _node_publish_mapper(weave_api.get(weave_api._merge(uri)))
            return _local_op_get_to_published_op_get(node)
    return node


def _node_is_op_get(node: graph.Node) -> bool:
    return isinstance(node, graph.OutputNode) and node.from_op.name == "get"


def _uri_of_get_node(node: graph.OutputNode) -> typing.Optional[str]:
    uri_node = node.from_op.inputs.get("uri")
    if isinstance(uri_node, graph.ConstNode) and isinstance(uri_node.val, str):
        return uri_node.val
    return None


def _uri_is_local_artifact(uri: str) -> bool:
    return uri.startswith("local-artifact://")


def _name_and_branch_from_node(
    node: typing.Optional[graph.Node],
) -> typing.Tuple[typing.Optional[str], typing.Optional[str]]:
    name: typing.Optional[str] = None
    version: typing.Optional[str] = None
    if node is not None and _node_is_op_get(node):
        uri_str = _uri_of_get_node(node)  # type: ignore
        if uri_str is not None:
            uri = WeaveURI.parse(uri_str)
            name = uri.name
            if uri.version is not None and not likely_commit_hash(uri.version):
                version = uri.version

    return (name, version)


def _local_op_get_to_pub_ref(node: graph.Node) -> ref_base.Ref:
    obj = weave_internal.use(node, context.get_client())
    name, version = _name_and_branch_from_node(node)

    return storage._direct_publish(
        obj, name, branch_name=version, assume_weave_type=node.type
    )


def _local_op_get_to_published_op_get(node: graph.Node) -> graph.Node:
    pub_ref = _local_op_get_to_pub_ref(node)
    new_node = ref_to_node(pub_ref)

    if new_node is None:
        raise errors.WeaveSerializeError(
            f"Failed to serialize {node} to published node"
        )

    return new_node


def _local_ref_to_published_ref(ref: ref_base.Ref) -> ref_base.Ref:
    node = ref_to_node(ref)

    if node is None:
        raise errors.WeaveSerializeError(f"Failed to serialize {ref} to published ref")
    return _local_op_get_to_pub_ref(node)
