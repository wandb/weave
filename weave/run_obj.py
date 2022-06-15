import time

from . import weave_types as types
from . import context
from . import artifacts_local
from . import uris
from .decorators import weave_class, op, mutation

_loading_builtins_token = context.set_loading_built_ins()


@weave_class(weave_type=types.RunType)
class Run:
    def __init__(
        self,
        _id,
        _op_name,
        _state=None,
        _prints=None,
        _history=None,
        _inputs=None,
        _output=None,
    ):
        self._id = _id
        self._op_name = _op_name
        self._state = _state
        if self._state is None:
            self._state = "pending"
        self._prints = _prints
        if self._prints is None:
            self._prints = []
        self._history = _history
        if self._history is None:
            self._history = []
        self._inputs = _inputs
        self._output = _output

    @op(
        name="run-setstate",
        input_type={
            "self": types.RunType(
                types.TypedDict({}), types.List(types.Any()), types.Any()
            ),
            "state": types.RUN_STATE_TYPE,
        },
        # can't return run because then we'll think this is an async op!
        output_type=types.Invalid(),
    )
    @mutation
    def set_state(self, state):
        self._state = state
        return self

    @op(
        name="run-print",
        input_type={
            "self": types.RunType(
                types.TypedDict({}), types.List(types.Any()), types.Any()
            ),
            "s": types.String(),
        },
        # can't return run because then we'll think this is an async op!
        output_type=types.Invalid(),
    )
    @mutation
    def print_(self, s):
        # print("PRINT s", s)
        self._prints.append(s)
        return self

    @op(
        name="run-log",
        input_type={
            "self": types.RunType(
                types.TypedDict({}), types.List(types.Any()), types.Any()
            ),
            "v": types.Any(),
        },
        # can't return run because then we'll think this is an async op!
        output_type=types.Invalid(),
    )
    @mutation
    def log(self, v):
        self._history.append(v)
        return self

    @mutation
    def set_inputs(self, v):
        self._inputs = v
        return self

    @op(
        name="run-setoutput",
        input_type={
            "self": types.RunType(
                types.TypedDict({}), types.List(types.Any()), types.Any()
            ),
            "v": types.Any(),
        },
        output_type=types.Invalid(),
    )
    @mutation
    def set_output(self, v):
        from . import storage

        # Force the output to be a ref.
        # TODO: this is probably not the right place to do this.
        if not isinstance(v, storage.Ref):
            v = storage.save(v)
        self._output = v
        return self

    @op(
        name="run-await",
        input_type={
            "self": types.RunType(
                types.TypedDict({}), types.List(types.Any()), types.Any()
            )
        },
        output_type=lambda input_types: input_types["self"]._output,
    )
    def await_final_output(self):
        sleep_mult = 1
        while self._state == "pending" or self._state == "running":

            sleep_time = 0.01 * sleep_mult
            if sleep_time > 1:
                sleep_time = 1
            sleep_mult *= 1.3

            from .ops_primitives.storage import get as op_get
            from .api import use

            # TODO: this should support full URIS instead of hard coding
            uri = uris.WeaveLocalArtifactURI.make_uri(
                artifacts_local.local_artifact_dir(), f"run-{self._id}", "latest"
            )
            self = use(op_get(uri))

        return self._output

    @op(
        input_type={
            "self": types.RunType(
                types.TypedDict({}), types.List(types.Any()), types.Any()
            ),
        },
        output_type=types.String(),
    )
    def id(self):
        return self._id

    @op(
        input_type={
            "self": types.RunType(
                types.TypedDict({}), types.List(types.Any()), types.Any()
            ),
        },
        output_type=types.RUN_STATE_TYPE,
    )
    def state(self):
        return self._state

    @op(
        input_type={
            "self": types.RunType(
                types.TypedDict({}), types.List(types.Any()), types.Any()
            ),
        },
        output_type=types.List(types.String()),
    )
    def prints(self):
        return self._prints

    @op(
        input_type={
            "self": types.RunType(
                types.TypedDict({}), types.List(types.Any()), types.Any()
            ),
        },
        output_type=lambda input_types: input_types["self"]._history,
    )
    def history(self):
        return self._history

    @op(
        name="run-output",
        input_type={
            "self": types.RunType(
                types.TypedDict({}), types.List(types.Any()), types.Any()
            ),
        },
        output_type=lambda input_types: input_types["self"]._output,
    )
    def output(self):
        return self._output


types.RunType.instance_classes = Run
types.RunType.instance_class = Run

context.clear_loading_built_ins(_loading_builtins_token)
