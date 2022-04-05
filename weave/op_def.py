import inspect
import os
import typing

from . import errors
from . import op_args
from . import weave_types


class OpDef(object):
    name: str
    input_type: op_args.OpArgs
    output_type: typing.Union[
        weave_types.Type,
        typing.Callable[[typing.Dict[str, weave_types.Type]], weave_types.Type],
    ]
    setter = str

    def __init__(
        self,
        name,
        input_type,
        output_type,
        call_fn,
        resolve_fn,
        setter=None,
        render_info=None,
        pure=True,
    ):
        self.name = name
        self.input_type = input_type
        self.output_type = output_type
        self.call_fn = call_fn
        self.resolve_fn = resolve_fn
        self.setter = setter
        self.render_info = render_info
        self.pure = pure

    @property
    def simple_name(self):
        # We need this to get around the run job_type 64 char limit, and artifact name limitations.
        # TODO: This function will need to be stable! Let's make sure we like what we're doing here.
        if self.name.startswith("file://"):
            # Shorten because local file paths tend to blow out the 64 char job_type limit (we need
            # to fix that probably)
            return self.name.rsplit("/", 1)[1]
        elif self.name.startswith("wandb-artifact://"):
            return (
                self.name[len("wandb-artifact://") :]
                .replace(":", ".")
                .replace("/", "_")
            )
        else:
            # This is for builtins, which I think we may just want to get rid
            # of?
            return self.name

    def to_dict(self):
        if callable(self.output_type):
            raise errors.WeaveSerializeError(
                "serializing op with callable output_type not yet implemented"
            )
        if self.input_type.kind != op_args.OpArgs.NAMED_ARGS:
            raise errors.WeaveSerializeError(
                "serializing op with non-named-args input_type not yet implemented"
            )

        input_types = {
            name: arg_type.to_dict()
            for name, arg_type in self.input_type.arg_types.items()
        }

        output_type = self.output_type.to_dict()

        serialized = {
            "name": self.name,
            "input_types": input_types,
            "output_type": output_type,
        }
        if self.render_info is not None:
            serialized["render_info"] = self.render_info

        return serialized

    def __str__(self):
        return "<OpDef: %s>" % self.name


def fully_qualified_opname(wrap_fn):
    op_module_file = os.path.abspath(inspect.getfile(wrap_fn))
    if op_module_file.endswith(".py"):
        op_module_file = op_module_file[:-3]
    elif op_module_file.endswith(".pyc"):
        op_module_file = op_module_file[:-4]
    return "file://" + op_module_file + "." + wrap_fn.__name__
