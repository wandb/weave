import textwrap
import contextlib
import contextvars
import inspect
import os
import typing
import sys

from . import errors
from . import op_args
from . import weave_types as types


from .artifacts_local import LOCAL_ARTIFACT_DIR


# Set to the op version if we're in the process of loading
# an op from an artifact.

_loading_op_version: contextvars.ContextVar[
    typing.Optional[str]
] = contextvars.ContextVar("loading_op_version", default=None)


@contextlib.contextmanager
def loading_op_version(version):
    token = _loading_op_version.set(version)
    yield _loading_op_version.get()
    _loading_op_version.reset(token)


def get_loading_op_version():
    return _loading_op_version.get()


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
    ):
        self.name = name
        self.input_type = input_type
        self.output_type = output_type
        self.resolve_fn = resolve_fn
        self.setter = setter
        self.render_info = render_info
        self.pure = pure
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
    def fullname(self):
        return self.name + ":" + self.version

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

    @property
    def is_mutation(self):
        return getattr(self.resolve_fn, "is_mutation", False)

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


def is_op_def(obj):
    return isinstance(obj, OpDef)


class OpDefType(types.Type):
    name = "op-def"
    instance_class = OpDef
    instance_classes = OpDef

    def __init__(self):
        # TODO: actually this should maybe be the function's type?
        pass

    def assign_type(self, other):
        return types.InvalidType()

    def save_instance(self, obj: OpDef, artifact, name):
        code = "import weave\n" "\n"
        code += textwrap.dedent(inspect.getsource(obj.resolve_fn))
        with artifact.new_file(f"{name}.py") as f:
            f.write(code)

    def load_instance(cls, artifact, name, extra=None):
        path = os.path.relpath(artifact.path(f"{name}"), start=LOCAL_ARTIFACT_DIR)

        # convert filename into module path
        parts = path.split("/")
        module_path = ".".join(parts)

        # This has a side effect of registering the op
        sys.path.insert(0, LOCAL_ARTIFACT_DIR)
        with loading_op_version(artifact.version):
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
