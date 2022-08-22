import dataclasses
import typing

from . import runs
from . import weave_types as types


@dataclasses.dataclass
class LocalRun(runs.Run):
    # TODO: we can maybe get rid of this attribute since mappers already
    # attaches the artifact the object came from.
    local_store: typing.Any = None

    def print_(self, s: str):
        self.prints.append(s)
        self.save()

    def set_output(self, v: typing.Any):
        # The output is always saved as an artifact, so we have a ref to it.
        # test_async_op_expr will fail without this line.
        self.output = self.local_store.save_object(v)
        self.save()

    def save(self):
        return self.local_store.save_run(self)


class RunLocalType(types.RunType):
    instance_classes = LocalRun
