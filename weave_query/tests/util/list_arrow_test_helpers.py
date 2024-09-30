from weave_query import api as weave
from weave_query import ops_arrow as arrow
from weave_query.ops_primitives import list_


class ListLikeNodeInterface:
    @staticmethod
    def make_node(value):
        raise NotImplementedError

    @staticmethod
    def use_node(node):
        raise NotImplementedError


class ListNode(ListLikeNodeInterface):
    @staticmethod
    def make_node(value):
        return list_.make_list(**{f"{i}": v for i, v in enumerate(value)})

    @staticmethod
    def use_node(node):
        return weave.use(node)


class ArrowNode(ListLikeNodeInterface):
    @staticmethod
    def make_node(value):
        return weave.save(arrow.to_arrow(value))

    @staticmethod
    def use_node(node):
        return weave.use(node).to_pylist_notags()


ListInterfaces = [ListNode, ArrowNode]
