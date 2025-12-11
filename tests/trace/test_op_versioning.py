import re
import typing
from collections.abc import Callable

import numpy as np
import pytest

import weave
import weave as wv
from weave.trace.op import as_op
from weave.trace.serialization.mem_artifact import MemTraceFilesArtifact
from weave.trace.serialization.op_type import save_instance
from weave.trace_server.trace_server_interface import FileContentReadReq, ObjReadReq
from weave.utils.project_id import to_project_id


def get_saved_code(client, ref):
    resp = client.server.obj_read(
        ObjReadReq(
            project_id=to_project_id(ref.entity, ref.project),
            object_id=ref.name,
            digest=ref.digest,
        )
    )
    files = resp.obj.val["files"]
    file_read_resp = client.server.file_content_read(
        FileContentReadReq(
            project_id=to_project_id(ref.entity, ref.project), digest=files["obj.py"]
        )
    )
    return file_read_resp.content.decode()


EXPECTED_SOLO_OP_CODE = """import numpy as np
import weave

@weave.op
def solo_versioned_op(a: int) -> float:
    # Rely on the "import numpy as np" import
    return np.array([a, a]).mean()
"""


def test_solo_op_versioning(client):
    from tests.trace import op_versioning_solo

    ref = weave.publish(op_versioning_solo.solo_versioned_op)

    saved_code = get_saved_code(client, ref)

    print("SAVED_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_SOLO_OP_CODE


EXPECTED_OBJECT_OP_CODE = """import numpy as np
import weave

@weave.op
def versioned_op(self, a: int) -> float:
    # Rely on the "import numpy as np" import
    return np.array([a, self.val]).mean()
"""


def test_object_op_versioning(client):
    from tests.trace import op_versioning_obj

    obj = op_versioning_obj.MyTestObjWithOp(val=5)
    # Call it to publish
    obj.versioned_op(5)
    ref = as_op(obj.versioned_op).ref

    saved_code = get_saved_code(client, ref)
    print("SAVED_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_OBJECT_OP_CODE


EXPECTED_IMPORTFROM_OP_CODE = """from numpy import array
import weave

@weave.op
def versioned_op_importfrom(a: int) -> float:
    return array([x + 1 for x in range(a)]).mean()
"""


def test_op_versioning_importfrom(client):
    from tests.trace import op_versioning_importfrom

    ref = weave.publish(op_versioning_importfrom.versioned_op_importfrom)
    saved_code = get_saved_code(client, ref)
    print("SAVE_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_IMPORTFROM_OP_CODE


def test_op_versioning_lotsofstuff():
    @weave.op
    def versioned_op_lotsofstuff(a: int) -> float:
        j = [x + 1 for x in range(a)]
        k = (y - 3 for y in j)
        return np.array(k).mean()


def test_op_versioning_inline_import(client):
    pass


def test_op_versioning_inline_func_decl():
    @weave.op
    def versioned_op_inline_func_decl(a: int) -> float:
        def inner_func(x):
            if x == 0:
                return 2
            # ensure recursion is handled
            return inner_func(x - 1) * 2

        return inner_func(a)


EXPECTED_CLOSURE_CONTANT_OP_CODE = """import weave

x = 10

@weave.op
def versioned_op_closure_constant(a: int) -> float:
    return a + x
"""


def test_op_versioning_closure_constant(client):
    x = 10

    @weave.op
    def versioned_op_closure_constant(a: int) -> float:
        return a + x

    ref = weave.publish(versioned_op_closure_constant)

    saved_code = get_saved_code(client, ref)
    print("SAVED_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_CLOSURE_CONTANT_OP_CODE


EXPECTED_CLOSURE_CONTANT_DICT_OP_CODE = """import weave

x = {
    "a": 5,
    "b": 10
}

@weave.op
def versioned_op_closure_constant(a: int) -> float:
    return a + x["a"]
"""


def test_op_versioning_closure_dict_simple(client):
    x = {"a": 5, "b": 10}

    @weave.op
    def versioned_op_closure_constant(a: int) -> float:
        return a + x["a"]

    ref = weave.publish(versioned_op_closure_constant)

    saved_code = get_saved_code(client, ref)

    print("SAVED CODE")
    print(saved_code)

    assert saved_code == EXPECTED_CLOSURE_CONTANT_DICT_OP_CODE


EXPECTED_CLOSURE_CONTANT_DICT_NP_OP_CODE = """import weave

x = {
    "a": 5,
    "b": weave.storage.artifact_path_ref('x/b').get()
}

@weave.op
def versioned_op_closure_constant(a: int) -> float:
    return a + x["b"].mean() + x["a"]
"""


@pytest.mark.skip("custom objs not working with new weave_client")
def test_op_versioning_closure_dict_np(client):
    x = {"a": 5, "b": np.array([1, 2, 3])}

    @weave.op
    def versioned_op_closure_constant(a: int) -> float:
        return a + x["b"].mean() + x["a"]

    ref = weave.publish(versioned_op_closure_constant)

    saved_code = get_saved_code(client, ref)

    print("SAVED CODE")
    print(saved_code)

    assert saved_code == EXPECTED_CLOSURE_CONTANT_DICT_NP_OP_CODE
    op2 = weave.ref(str(ref)).get()
    assert op2(1) == 8


EXPECTED_CLOSURE_CONTANT_DICT_OPS_OP_CODE = """import weave

x = {
    "a": weave.ref('weave:///shawn/test-project/op/op-cat:nLZYziGZnZ1yH6rlCrDPUifoFwvqRo5oTDcN1xMFVD4').get(),
    "b": weave.ref('weave:///shawn/test-project/op/op-dog:BGOgiFNzkGvtqGmdbRHcpcZnOuZp5ISyjesyJHCl9oI').get(),
    "c": weave.ref('weave:///shawn/test-project/op/op-dog:BGOgiFNzkGvtqGmdbRHcpcZnOuZp5ISyjesyJHCl9oI').get()
}

@weave.op
def pony(v: int):
    v = x["a"](v)
    v = x["b"](v)
    v = x["c"](v)
    print("hello from pony()")
    return v + 99
"""


@pytest.mark.skip("failing in ci, due to some kind of /tmp file slowness?")
def test_op_versioning_closure_dict_ops(client):
    @weave.op
    def cat(v: int):
        print("hello from cat()")
        return v + 1

    @weave.op
    def dog(v: int):
        print("hello from dog()")
        return v - 1

    x = {"a": cat, "b": dog, "c": dog}

    @weave.op
    def pony(v: int):
        v = x["a"](v)
        v = x["b"](v)
        v = x["c"](v)
        print("hello from pony()")
        return v + 99

    ref = weave.publish(pony)

    saved_code = get_saved_code(client, ref)

    print("SAVED CODE")
    print(saved_code)

    assert saved_code == EXPECTED_CLOSURE_CONTANT_DICT_OPS_OP_CODE
    op2 = weave.ref(str(ref)).get()
    assert op2(1) == 99


EXPECTED_MIXED_OP_CODE = """import weave
import numpy as np

dog = weave.ref('weave:///shawn/test-project/op/op-dog:BGOgiFNzkGvtqGmdbRHcpcZnOuZp5ISyjesyJHCl9oI').get()

x = {
    "a": weave.ref('weave:///shawn/test-project/op/op-cat:nLZYziGZnZ1yH6rlCrDPUifoFwvqRo5oTDcN1xMFVD4').get(),
    "b": weave.storage.artifact_path_ref('x/b').get()
}

@weave.op
def pony(v: int):
    v = dog(v)
    v = x["a"](v) + x["b"].mean()
    v = np.array([v, v, v]).mean()

    print("hello from pony()")
    return v + 99
"""


@pytest.mark.skip("custom objs not working with new weave_client")
def test_op_versioning_mixed(client):
    @weave.op
    def cat(v: int):
        print("hello from cat()")
        return v + 1

    @weave.op
    def dog(v: int):
        print("hello from dog()")
        return v - 1

    x = {"a": cat, "b": np.array([1, 2, 3])}

    @weave.op
    def pony(v: int):
        v = dog(v)
        v = x["a"](v) + x["b"].mean()
        v = np.array([v, v, v]).mean()

        print("hello from pony()")
        return v + 99

    ref = weave.publish(pony)

    saved_code = get_saved_code(client, ref)

    print("SAVED CODE")
    print(saved_code)

    assert saved_code == EXPECTED_MIXED_OP_CODE
    op2 = weave.ref(str(ref)).get()
    assert op2(1) == 102.0


def test_op_versioning_exception():
    # Just ensure this doesn't raise by running it.
    @weave.op
    def versioned_op_exception(a: int) -> float:
        try:
            x = 1 / 0
        except Exception as e:
            print("E", e)
            return 9999
        return x


def test_op_versioning_2ops(client):
    @weave.op
    def dog():
        print("hello from dog()")

    @weave.op
    def cat():
        print("hello from cat()")
        dog()
        dog()

    cat()

    ref = as_op(cat).ref

    saved_code = get_saved_code(client, ref)


EXPECTED_TYPEDICT_ANNO_CODE = """import typing
import weave

class SomeDict(typing.TypedDict):
    val: int

@weave.op
def some_d(v: int) -> SomeDict:
    return SomeDict(val=v)
"""


def test_op_return_typeddict_annotation(
    client,
):
    class SomeDict(typing.TypedDict):
        val: int

    @weave.op
    def some_d(v: int) -> SomeDict:
        return SomeDict(val=v)

    assert some_d(1) == {"val": 1}

    ref = as_op(some_d).ref
    assert ref is not None

    saved_code = get_saved_code(client, ref)
    print("SAVED_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_TYPEDICT_ANNO_CODE

    op2 = weave.ref(ref.uri()).get()
    assert op2(2) == {"val": 2}


EXPECTED_RETURN_CUSTOM_CLASS_CODE = """import weave

class MyCoolClass:
    val: int

    def __init__(self, val):
        self.val = val

@weave.op
def some_d(v: int):
    return MyCoolClass(v)
"""


def test_op_return_return_custom_class(
    client,
):
    class MyCoolClass:
        val: int

        def __init__(self, val):
            self.val = val

    @weave.op
    def some_d(v: int):
        return MyCoolClass(v)

    assert some_d(1).val == 1

    ref = as_op(some_d).ref
    assert ref is not None

    saved_code = get_saved_code(client, ref)
    print("SAVED_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_RETURN_CUSTOM_CLASS_CODE


EXPECTED_NESTED_FUNCTION_CODE = """import weave

@weave.op
def some_d(v: int):
    def internal_fn(x):
        return x + 3

    return internal_fn(v)
"""


def test_op_nested_function(
    client,
):
    @weave.op
    def some_d(v: int):
        def internal_fn(x):
            return x + 3

        return internal_fn(v)

    assert some_d(1) == 4

    ref = as_op(some_d).ref
    assert ref is not None

    saved_code = get_saved_code(client, ref)
    print("SAVED_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_NESTED_FUNCTION_CODE
    assert weave.ref(ref.uri()).get()(2) == 5


def test_op_basic_execution(client):
    @weave.op
    def adder(v: int) -> int:
        return v + 1

    assert adder(1) == 2

    ref = as_op(adder).ref
    assert ref is not None

    op2 = weave.ref(ref.uri()).get()
    assert op2(2) == 3


class SomeOtherClass:
    pass


class SomeClass:
    def some_fn(self):
        return SomeOtherClass()


EXPECTED_NO_REPEATS_CODE = """import weave

class SomeOtherClass:
    pass

class SomeClass:
    def some_fn(self):
        return SomeOtherClass()

@weave.op
def some_d(v):
    a = SomeOtherClass()
    b = SomeClass()
    return SomeClass()
"""


def test_op_no_repeats(client):
    @weave.op
    def some_d(v):
        a = SomeOtherClass()
        b = SomeClass()
        return SomeClass()

    some_d(SomeClass())
    ref = as_op(some_d).ref
    assert ref is not None

    saved_code = get_saved_code(client, ref)
    print(saved_code)

    assert saved_code == EXPECTED_NO_REPEATS_CODE


EXPECTED_INSTANCE_CODE = """import weave

instance = "<test_op_versioning.test_op_instance.<locals>.MyClass object at 0x000000000>"

@weave.op
def t(text: str):
    print(instance._version)
    return text
"""


def test_op_instance(client):
    class MyClass:
        _version: str
        api_key: str

        def __init__(self, secret: str) -> None:
            self._version = "1.0.0"
            self.api_key = secret

    # We want to make sure this secret value is not saved in the code
    instance = MyClass("sk-1234567890qwertyuiop")

    @weave.op
    def t(text: str):
        print(instance._version)
        return text

    t("hello")

    ref = as_op(t).ref
    assert ref is not None

    saved_code = get_saved_code(client, ref)
    print("SAVED CODE")
    print(saved_code)

    # Instance address expected to change each run
    clean_saved_code = re.sub(r"0x[0-9a-fA-F]+", "0x000000000", saved_code)

    assert clean_saved_code == EXPECTED_INSTANCE_CODE


EXPECTED_IMPORT_AS_CODE = """import json as js
import weave

@weave.op
def func(data: dict) -> str:
    return js.dumps(data)
"""


def test_op_import_as(client):
    import json as js

    @weave.op
    def func(data: dict) -> str:
        return js.dumps(data)

    func({"a": 1})

    ref = as_op(func).ref
    assert ref is not None

    saved_code = get_saved_code(client, ref)
    print(saved_code)

    assert saved_code == EXPECTED_IMPORT_AS_CODE


EXPECTED_IMPORT_FROM_AS_CODE = """from json import dumps as ds
import weave

@weave.op
def func(data: dict) -> str:
    return ds(data)
"""


def test_op_import_from_as(client):
    from json import dumps as ds

    @weave.op
    def func(data: dict) -> str:
        return ds(data)

    func({"a": 1})

    ref = as_op(func).ref
    assert ref is not None

    saved_code = get_saved_code(client, ref)
    print(saved_code)

    assert saved_code == EXPECTED_IMPORT_FROM_AS_CODE


def save_and_get_code(func: Callable) -> str:
    artifact = MemTraceFilesArtifact()
    save_instance(func, artifact, "obj")
    saved_code = artifact.path_contents["obj.py"]
    if isinstance(saved_code, bytes):
        saved_code = saved_code.decode()
    return saved_code


STANDARD_FUNC_CODE = """import weave

@weave.op
def standard_func(): ...
"""


def test_standard_import():
    """Test that standard import weave works correctly."""

    @weave.op
    def standard_func(): ...

    code = save_and_get_code(standard_func)
    assert code == STANDARD_FUNC_CODE


ALIASED_FUNC_CODE = """import weave as wv

@wv.op
def aliased_func(): ...
"""


def test_aliased_import_wv():
    """Test that aliased import (wv) is handled correctly - should preserve the alias."""

    @wv.op
    def aliased_func(): ...

    code = save_and_get_code(aliased_func)
    assert code == ALIASED_FUNC_CODE


PAREN_FUNC_CODE = """import weave as wv

@wv.op
def paren_func(): ...
"""


def test_op_with_parentheses():
    """Test that @wv.op() with parentheses is normalized to @wv.op - should preserve the alias."""

    @wv.op()
    def paren_func(): ...

    code = save_and_get_code(paren_func)
    assert code == PAREN_FUNC_CODE
