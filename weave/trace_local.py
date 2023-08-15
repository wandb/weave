import hashlib
import typing
from typing import Mapping
import json
import dataclasses
import random

from . import storage
from . import ref_base
from . import op_def
from . import weave_types as types
from . import runs
from . import graph
from . import artifact_local
from . import weave_internal
from . import op_policy


@dataclasses.dataclass
class RunKey:
    op_simple_name: str
    id: str


def _value_id(val):
    # Important, do not include the type here, as it can change.
    # This happens because you can have a ref to an item that's in a list.
    # The list's object_type can change as items are appended to it.
    # We don't know the specific type of each item within the list without
    # further refinement.
    hash_val = json.dumps(storage.to_python(val)["_val"])
    hash = hashlib.md5()
    hash.update(json.dumps(hash_val).encode())
    return hash.hexdigest()


def make_run_key(
    op_def: op_def.OpDef,
    inputs_refs: Mapping[str, typing.Any],
    impure_cache_key: typing.Optional[str] = None,
) -> RunKey:
    hash_val: typing.Any
    if not op_def.pure and impure_cache_key is None:
        hash_val = random.random()
    else:
        hashable_inputs = {}
        for name, obj in inputs_refs.items():
            hashable_inputs[name] = _value_id(obj)
        hash_val = {
            "op_name": op_def.name,
            "op_version": op_def.version,
            "inputs": hashable_inputs,
        }
        if impure_cache_key is not None:
            hash_val["impure_cache_key"] = impure_cache_key
    hash = hashlib.md5()
    hash.update(json.dumps(hash_val).encode())

    # For now, put op_def name in the run ID. This makes debugging much
    # easier because you can inspect the local artifact directly names.
    # This may not be what we want in production.
    return RunKey(op_def.simple_name, hash.hexdigest())


# Trace interface. Makes use of objects and mutations to store trace data.
# Manually constructs nodes and op calls to avoid recursively calling
# the execute engine, either via use or type refinement.
class TraceLocal:
    def new_run(
        self,
        run_key: RunKey,
        inputs: typing.Optional[dict[str, ref_base.Ref]] = None,
        output: typing.Any = None,
    ) -> graph.Node[runs.Run]:
        run = runs.Run(run_key.id, run_key.op_simple_name)
        if inputs is not None:
            run.inputs = inputs
        if output is not None:
            run.output = output
        self.save_run(run)
        return self.get_run(run_key)

    def _single_run(self, run_key: RunKey) -> graph.Node[runs.Run]:
        single_uri = artifact_local.WeaveLocalArtifactURI(
            f"run-{run_key.op_simple_name}-{run_key.id}", "latest", "obj"
        )
        return weave_internal.manual_call(
            "get",
            {"uri": graph.ConstNode(types.String(), str(single_uri))},
            types.RunType(),
        )

    def _run_table(self, run_key: RunKey):
        table_uri = artifact_local.WeaveLocalArtifactURI(
            f"run-{run_key.op_simple_name}", "latest", "obj"
        )
        return weave_internal.manual_call(
            "get",
            {"uri": graph.ConstNode(types.String(), str(table_uri))},
            types.List(types.RunType()),
        )

    def _should_save_to_table(self, run_key: RunKey):
        # Restricted to just a couple ops for now.
        # A NOTE: for the future, async ops definitely can't be saved to
        # table (until we have safe table writes)
        return op_policy.should_table_cache(run_key.op_simple_name)

    def get_run(self, run_key: RunKey) -> graph.Node[runs.Run]:
        if self._should_save_to_table(run_key):
            return weave_internal.manual_call(
                "listobject-lookup",
                {
                    "arr": self._run_table(run_key),
                    "id": graph.ConstNode(types.String(), run_key.id),
                },
                types.RunType(),
            )
        return self._single_run(run_key)

    def get_run_val(self, run_key: RunKey) -> typing.Optional[runs.Run]:
        from . import execute_fast

        res = execute_fast._execute_fn_no_engine(None, None, self.get_run(run_key))
        return res

    def save_run(self, run: runs.Run):
        from .ops_primitives import weave_api

        run_key = RunKey(run.op_name, run.id)
        if self._should_save_to_table(run_key):
            weave_api.append(self._run_table(run_key), run, {})
        else:
            weave_api.set(self._single_run(run_key), run, {})

    def save_run_output(self, od: op_def.OpDef, run_key: RunKey, output: typing.Any):
        if not od.pure:
            # If an op is impure, its output is saved to a name that does not
            # include run ID. This means consuming pure runs will hit cache if
            # the output of an impure op is the same as it was last time.
            # However that also means we can traceback through impure ops if we want
            # to see the actual query that run for a given object.
            # TODO: revisit this behavior
            return self.save_object(output)
        # TODO: table caching is currently disabled, but this path doesn't handle it
        # when we turn it back on!
        return self.save_object(
            output, name=f"run-{run_key.op_simple_name}-{run_key.id}-output"
        )

    def save_object(
        self, obj: typing.Any, name: typing.Optional[str] = None
    ) -> ref_base.Ref:
        return storage.save(obj, name=name, branch="latest")
