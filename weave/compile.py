import typing

from . import weave_types as types
from . import graph
from . import graph_editable
from . import registry_mem


def await_run_outputs(nodes: typing.List[graph.Node]):
    """Automatically insert Run.await_final_output steps as needed."""
    from . import run_obj

    edit_g = graph_editable.EditGraph()
    for node in nodes:
        edit_g.add_node(node)

    for edge in edit_g.edges:
        actual_input_type = edge.output_of.type
        op_def = registry_mem.memory_registry.get_op(edge.input_to.from_op.name)
        if op_def.has_varargs:
            # TODO: This is not
            continue
        expected_input_type = op_def.input_type[edge.input_name]
        if isinstance(actual_input_type, types.RunType) and not isinstance(
            expected_input_type, types.RunType
        ):
            if (
                expected_input_type.assign_type(actual_input_type._output)
                == types.Invalid()
            ):
                raise Exception(
                    "invalid type chaining for run. input_type: %s, op_input_type: %s"
                    % (actual_input_type, expected_input_type)
                )
            new_inputs = dict(edge.input_to.from_op.inputs)
            new_inputs[edge.input_name] = run_obj.Run.await_final_output(edge.output_of)
            edit_g.replace(
                edge.input_to,
                graph.OutputNode(
                    edge.input_to.type, edge.input_to.from_op.name, new_inputs
                ),
            )

    return [edit_g.get_node(n) for n in nodes]


def compile(nodes: typing.List[graph.Node]):
    nodes = await_run_outputs(nodes)
    return nodes
