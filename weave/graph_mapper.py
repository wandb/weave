from . import graph
from . import mappers
from . import ref_base
from . import mappers_python_def as mappers_python
from . import node_ref
from . import weave_types as types


class FunctionToPyFunction(mappers.Mapper):
    def apply(self, obj):
        # TODO: This should be a check on input type rather than a value check!
        #   As implemented it might be possible to save in two different formats
        #   for the save input type, which is bad.
        return obj.to_json()


class PyFunctionToFunction(mappers.Mapper):
    def apply(self, obj):
        if isinstance(obj, str):
            ref = ref_base.Ref.from_str(obj)
            return node_ref.ref_to_node(ref)
        # Obj is graph.Node
        return graph.Node.node_from_json(obj)


mappers_python.add_mapper(types.Function, FunctionToPyFunction, PyFunctionToFunction)
