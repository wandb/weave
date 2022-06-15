import textwrap
import inspect
import os
import typing
import sys

from . import artifacts_local
from . import errors
from . import op_args
from . import context
from . import weave_types as types
from . import uris


class OpDef:
    """An Op Definition.

    Must be immediately passed to Register.register_op() after construction.
    """

    name: str
    input_type: op_args.OpArgs
    output_type: typing.Union[
        types.Type,
        typing.Callable[[typing.Dict[str, types.Type]], types.Type],
    ]
    setter = str
    call_fn: typing.Any
    version: typing.Optional[str]
    is_builtin: bool = False

    def __init__(
        self,
        name: str,
        input_type: op_args.OpArgs,
        output_type: typing.Union[
            types.Type,
            typing.Callable[[typing.Dict[str, types.Type]], types.Type],
        ],
        resolve_fn,
        setter=None,
        render_info=None,
        pure=True,
        is_builtin: typing.Optional[bool] = None,
    ):
        self.name = name
        self.input_type = input_type
        self.output_type = output_type
        self.resolve_fn = resolve_fn
        self.setter = setter
        self.render_info = render_info
        self.pure = pure
        self.is_builtin = (
            is_builtin if is_builtin is not None else context.get_loading_built_ins()
        )
        self.version = None
        self.lazy_call = None
        self.eager_call = None
        self.call_fn = None
        self.instance = None

    def __get__(self, instance, owner):
        # This is part of Python's descriptor protocol, and when this op_def
        # is fetched as a member of a class
        self.instance = instance
        return self

    def __call__(self, *args, **kwargs):
        if self.instance is not None:
            return self.call_fn(self.instance, *args, **kwargs)
        return self.call_fn(*args, **kwargs)

    @property
    def uri(self):
        return self.name

    @property
    def simple_name(self):
        return uris.WeaveURI.parse(self.name).full_name

    @property
    def is_mutation(self):
        return getattr(self.resolve_fn, "is_mutation", False)

    @property
    def is_async(self):
        return not callable(self.output_type) and self.output_type.name == "run-type"

    def to_dict(self):
        if callable(self.output_type):
            raise errors.WeaveSerializeError(
                "serializing op with callable output_type not yet implemented"
            )
        if self.input_type.kind != op_args.OpArgs.NAMED_ARGS:
            raise errors.WeaveSerializeError(
                "serializing op with non-named-args input_type not yet implemented"
            )
        input_types = self.input_type.to_dict()
        output_type = self.output_type.to_dict()

        serialized = {
            "name": self.uri,
            "input_types": input_types,
            "output_type": output_type,
        }
        if self.render_info is not None:
            serialized["render_info"] = self.render_info

        return serialized

    def __str__(self):
        return "<OpDef: %s>" % self.name


def is_op_def(obj):
    return isinstance(obj, OpDef)


class OpDefType(types.Type):
    name = "op-def"
    instance_class = OpDef
    instance_classes = OpDef

    input_type: op_args.OpArgs
    output_type: types.Type

    def __init__(self, input_type: op_args.OpArgs, output_type: types.Type):
        # TODO: actually this should maybe be the function's type?
        if callable(output_type):
            raise errors.WeaveTypeError(
                "OpDefType does not support Callable output_type yet"
            )

        self.input_type = input_type
        self.output_type = output_type

    def _to_dict(self):
        return {
            "input_type": self.input_type.to_dict(),
            "output_type": self.output_type.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: typing.Any):
        input_type = op_args.OpArgs.from_dict(d["input_type"])
        output_type = types.TypeRegistry.type_from_dict(d["output_type"])

        return cls(input_type, output_type)

    @classmethod
    def type_of_instance(cls, obj: OpDef):
        # TODO: fix output_type to support callable
        return cls(obj.input_type, obj.output_type)  # type: ignore

    def assign_type(self, other):
        return types.InvalidType()

    def save_instance(self, obj: OpDef, artifact, name):
        code = "import weave\n" "\n"
        code += textwrap.dedent(inspect.getsource(obj.resolve_fn))
        with artifact.new_file(f"{name}.py") as f:
            f.write(code)

    def load_instance(cls, artifact, name, extra=None):
        path_with_ext = os.path.relpath(
            artifact.path(f"{name}.py"), start=artifacts_local.local_artifact_dir()
        )
        # remove the .py extension
        path = os.path.splitext(path_with_ext)[0]
        # convert filename into module path
        parts = path.split("/")
        module_path = ".".join(parts)

        sys.path.insert(0, artifacts_local.local_artifact_dir())
        with context.loading_op_location(artifact.location):
            # This has a side effect of registering the op
            mod = __import__(module_path)
        sys.path.pop(0)
        # We justed imported e.g. 'op-number-add.xaybjaa._obj'. Navigate from
        # mod down to _obj.
        for part in parts[1:]:
            mod = getattr(mod, part)

        op_defs = inspect.getmembers(mod, is_op_def)
        if len(op_defs) != 1:
            raise errors.WeaveInternalError(
                "Unexpected Weave module saved in: %s" % path
            )
        _, od = op_defs[0]
        return od


def fully_qualified_opname(wrap_fn):
    op_module_file = os.path.abspath(inspect.getfile(wrap_fn))
    if op_module_file.endswith(".py"):
        op_module_file = op_module_file[:-3]
    elif op_module_file.endswith(".pyc"):
        op_module_file = op_module_file[:-4]
    return "file://" + op_module_file + "." + wrap_fn.__name__
