from ..op_def import OpDef
from ..op_def_type import OpDefType
from .. import weave_types as types
from .. import api as weave
from .. import op_args
from .. import errors


@weave.weave_class(weave_type=OpDefType)
class OpDefNodeMethods:
    # Unfortunate: we can't call this "name" because name is a
    # VarNode attribute. TODO: Fix
    @weave.op()
    def op_name(self) -> str:
        return self.simple_name  # type: ignore

    @weave.op()
    def input_type(self) -> dict[str, types.Type]:
        if not isinstance(self.input_type, op_args.OpNamedArgs):
            raise errors.WeaveInternalError(
                "OpDef.params not yet implemented for non-NamedArgs"
            )
        return self.input_type.arg_types

    @weave.op()
    def output_type(self) -> types.Type:
        if callable(self.output_type):
            return types.Invalid()
        return self.output_type
