import dataclasses
import logging
import typing

from .environment import strict_mode
from . import graph, op_def, op_args, debug_types
from . import weave_types as types
from .language_features.tagging.tagged_value_type import TaggedValueType

def log_safe(
    node: graph.Node, op_def: op_def.OpDef, inputs: dict[str, typing.Any], result: typing.Any
) -> None:
    try:
        if strict_mode():
            _log(node, op_def, inputs, result)
        pass
    except:
        return


@dataclasses.dataclass
class _StrictDebugLog:
    node: graph.Node
    op_def: op_def.OpDef
    inputs: dict[str, typing.Any]
    result: typing.Any


    def analyze(self) -> typing.Optional[str]:
        if not isinstance(self.node, graph.OutputNode):
            return None
        
        result_messages = []
        input_type_args = self.op_def.input_type
        if isinstance(input_type_args, op_args.OpNamedArgs):
            provided_input_types = self.node.from_op.input_types.values()
            provided_input_values = self.inputs
            provided_input_value_type = typing.cast(types.TypedDict, types.TypeRegistry.type_of(provided_input_values)).property_types.values()
            expected_input_type = input_type_args.arg_types

            input_arg_names = expected_input_type.keys()

            for input_key, (expected, provided, value_type) in zip(
                input_arg_names, zip(expected_input_type.values(), provided_input_types, provided_input_value_type)
            ):
                res = debug_types.why_not_assignable(expected, provided)
                if res:
                    result_messages.append(
                        f"Input {input_key} op_def.assign(graph): {res}"
                    )
                res = debug_types.why_not_assignable(expected, value_type)
                if res:
                    result_messages.append(
                        f"Input {input_key} op_def.assign(value): {res}"
                    )
                if isinstance(provided, types.Const):
                    value_type = types.Const(value_type, provided_input_values[input_key])
                res = debug_types.why_not_assignable(provided, value_type)
                if res:
                    result_messages.append(
                        f"Input {input_key} graph.assign(value): {res}"
                    )
        if len(result_messages) > 0:
            new_line = "\n\t"
            return f"OpDef {self.op_def.name} failed strict mode: {new_line}{new_line.join(result_messages)}"
        return None
        
        # provided_output_type = self.node.type
        # provided_output_value = self.result
        # provided_output_value_type = types.TypeRegistry.type_of(provided_output_value)
        # expected_output_type = self.op_def.unrefined_output_type_for_params(self.node.from_op.inputs)



        # for input_key, input_type, input_value in zip(node.from_)


def _logging_writer(payload: str) -> None:
    logging.info(payload)
    print(payload)



def _log(
    node: graph.Node, op_def: op_def.OpDef, inputs: dict[str, typing.Any], result: typing.Any
) -> None:
    try:
        res = _StrictDebugLog(node, op_def, inputs, result)
        analysis_results = _StrictDebugLog.analyze(res)
        if analysis_results is not None:
            _logging_writer(analysis_results)
    except Exception as e:
        _logging_writer(e)
    # Throwing away res for now... could be interesting to look at things in aggregate