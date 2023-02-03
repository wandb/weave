import hashlib
import typing
from typing import Mapping
import json
import random

from . import storage
from . import runs_local
from . import ref_base
from . import op_def
from . import errors


def _value_id(val):
    try:
        hash_val = json.dumps(storage.to_hashable(val))
    except errors.WeaveSerializeError:
        # This is a lame fallback. We will fall back here if an object
        # contains a reference to a custom type. When we generate a random
        # ID, nothing downstream of us will be cacheable.
        # It'd be better to not even try to serialize this object, and warn.
        # TODO: Fix later.
        hash_val = random.random()
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
    ) -> ref_base.Ref:
        return storage.save(obj, name=name)
