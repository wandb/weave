from collections.abc import Mapping
import json
import hashlib
import typing
from . import registry_mem
from . import storage
import random


def value_id(val):
    hash_val = json.dumps(storage.to_python(val))
    hash = hashlib.md5()
    hash.update(json.dumps(hash_val).encode())
    return hash.hexdigest()


def make_run_id(op_def: registry_mem.OpDef, inputs_refs: Mapping[str, typing.Any]):
    if not op_def.pure:
        hash_val = random.random()
    else:
        hashable_inputs = {}
        for name, obj in inputs_refs.items():
            ref = storage._get_ref(obj)
            if ref is not None:
                hashable_inputs[name] = str(ref)
            else:
                hashable_inputs[name] = value_id(obj)
        hash_val = {"op_name": op_def.name, "inputs": hashable_inputs}
    hash = hashlib.md5()
    hash.update(json.dumps(hash_val).encode())

    # For now, put op_def name in the run ID. This makes debugging much
    # easier because you can inspect the local artifact directly names.
    # This may not be what we want in production.
    return "%s-%s" % (op_def.simple_name, hash.hexdigest())
