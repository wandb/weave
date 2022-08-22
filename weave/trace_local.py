import hashlib
import typing
from typing import Mapping
import json
import random

from . import storage
from . import errors
from . import runs_local
from . import refs
from . import op_def


def _value_id(val):
    hash_val = json.dumps(storage.to_python(val))
    hash = hashlib.md5()
    hash.update(json.dumps(hash_val).encode())
    return hash.hexdigest()


def make_run_id(op_def: op_def.OpDef, inputs_refs: Mapping[str, typing.Any]) -> str:
    hash_val: typing.Any
    if not op_def.pure:
        hash_val = random.random()
    else:
        hashable_inputs = {}
        for name, obj in inputs_refs.items():
            ref = storage._get_ref(obj)
            if ref is not None:
                hashable_inputs[name] = str(ref)
            else:
                hashable_inputs[name] = _value_id(obj)
        hash_val = {
            "op_name": op_def.name,
            "op_version": op_def.version,
            "inputs": hashable_inputs,
        }
    hash = hashlib.md5()
    hash.update(json.dumps(hash_val).encode())

    # For now, put op_def name in the run ID. This makes debugging much
    # easier because you can inspect the local artifact directly names.
    # This may not be what we want in production.
    return "%s-%s" % (op_def.simple_name, hash.hexdigest())


class TraceLocal:
    @classmethod
    def _run_artifact_name(cls, run_id: str) -> str:
        return f"run-{run_id}"

    def new_run(self, run_id: str, op_name: str) -> runs_local.LocalRun:
        run = runs_local.LocalRun(run_id, op_name)
        run.local_store = self
        return run

    def get_run(self, run_id: str) -> typing.Optional[runs_local.LocalRun]:
        run = storage.get_local_version(self._run_artifact_name(run_id), "latest")
        if run is None:
            return None
        run.local_store = self
        return run

    def save_run(self, run: runs_local.LocalRun):
        return self.save_object(run, name=self._run_artifact_name(run.id))

    def save_object(
        self, obj: typing.Any, name: typing.Optional[str] = None
    ) -> refs.Ref:
        try:
            # Passing the node.type through here will really speed things up!
            # But we can't do it yet because Weave Python function aren't all
            # correctly typed, and WeaveJS sends down different types (like TagValues)
            # TODO: Fix
            return storage.save(obj, name=name)
        except errors.WeaveSerializeError:
            # Not everything can be serialized currently. But instead of storing
            # the result directly here, we save a MemRef with the same run_artifact_name.
            # This is required to make downstream run_ids path dependent.
            return storage.save_mem(obj, name=name)
