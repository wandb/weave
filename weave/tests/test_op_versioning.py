import pytest
import shutil
from .. import api as weave
from .. import artifact_fs
from .. import op_def
from .. import derive_op
import numpy as np
import typing


def test_op_versioning_saveload():
    @weave.op()
    def versioned_op(a: int, b: int) -> int:
        return a + b

    assert weave.use(versioned_op(1, 2)) == 3

    @weave.op()
    def versioned_op(a: int, b: int) -> int:
        return a - b

    # Because it is a new version with different code, this
    # should not hit memoized cache.
    assert weave.use(versioned_op(1, 2)) == -1

    v0_ref = weave.versions(versioned_op)[0]
    v0 = v0_ref.get()
    assert weave.use(v0(1, 2)) == 3

    # This should refer to v1, even though we just loaded v0
    v_latest = weave.use(weave.get("local-artifact:///op-versioned_op:latest/obj"))
    assert weave.use(v_latest(4, 20)) == -16

    v1_ref = weave.versions(versioned_op)[1]
    v1 = v1_ref.get()
    assert weave.use(v1(1, 2)) == -1

    v0_again = weave.use(
        weave.get(f"local-artifact:///op-versioned_op:{v0.version}/obj")
    )
    assert weave.use(v0_again(5, 6)) == 11


EXPECTED_SOLO_OP_CODE = """import weave
import numpy as np

@weave.op()
def solo_versioned_op(a: int) -> float:
    # Rely on the "import numpy as np" import
    return np.array([a, a]).mean()
"""


def test_solo_op_versioning(strict_op_saving):
    from . import op_versioning_solo

    with weave.local_client():
        ref = weave.publish(op_versioning_solo.solo_versioned_op)
    assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

    with ref.artifact.open("obj.py") as f:
        saved_code = f.read()

    print("SAVED_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_SOLO_OP_CODE


EXPECTED_OBJECT_OP_CODE = """import weave
import numpy as np

@weave.op()
def versioned_op(self, a: int) -> float:
    # Rely on the "import numpy as np" import
    return np.array([a, self.val]).mean()
"""


def test_object_op_versioning(strict_op_saving):
    from . import op_versioning_obj

    ref = weave.obj_ref(op_versioning_obj.MyTestObjWithOp.versioned_op)
    assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

    with ref.artifact.open("obj.py") as f:
        saved_code = f.read()
    print("SAVED_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_OBJECT_OP_CODE


EXPECTED_IMPORTFROM_OP_CODE = """import weave
from numpy import array

@weave.op()
def versioned_op_importfrom(a: int) -> float:
    return array([x + 1 for x in range(a)]).mean()
"""


def test_op_versioning_importfrom(strict_op_saving):
    from . import op_versioning_importfrom

    with weave.local_client():
        ref = weave.publish(op_versioning_importfrom.versioned_op_importfrom)
    assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

    with ref.artifact.open("obj.py") as f:
        saved_code = f.read()
    print("SAVE_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_IMPORTFROM_OP_CODE


def test_op_versioning_lotsofstuff(strict_op_saving):
    @weave.op()
    def versioned_op_lotsofstuff(a: int) -> float:
        j = [x + 1 for x in range(a)]
        k = map(lambda y: y - 3, j)
        return np.array(k).mean()


@pytest.mark.skip("Derived op not fully serializable due to non-json stuff in closure")
def test_op_versioning_higherlevel_function(strict_op_saving):
    @weave.op()
    def versioned_op_lowerlevel(a: int) -> float:
        return a + 1

    derive_op.MappedDeriveOpHandler.make_derived_op(versioned_op_lowerlevel)


def test_op_versioning_inline_import(strict_op_saving):
    from . import op_versioning_inlineimport


def test_op_versioning_inline_func_decl(strict_op_saving):
    @weave.op()
    def versioned_op_inline_func_decl(a: int) -> float:
        def inner_func(x):
            if x == 0:
                return 2
            # ensure recursion is handled
            return inner_func(x - 1) * 2

        return inner_func(a)


EXPECTED_CLOSURE_CONTANT_OP_CODE = """import weave

x = 10

@weave.op()
def versioned_op_closure_constant(a: int) -> float:
    return a + x
"""


def test_op_versioning_closure_contant(strict_op_saving):
    x = 10

    @weave.op()
    def versioned_op_closure_constant(a: int) -> float:
        return a + x

    ref = weave.obj_ref(versioned_op_closure_constant)
    with weave.local_client():
        ref = weave.publish(versioned_op_closure_constant)
    assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

    with ref.artifact.open("obj.py") as f:
        saved_code = f.read()
    print("SAVED_CODE")
    print(saved_code)

    assert saved_code == EXPECTED_CLOSURE_CONTANT_OP_CODE


EXPECTED_CLOSURE_CONTANT_DICT_OP_CODE = """import weave

x = {
    "a": 5,
    "b": 10
}

@weave.op()
def versioned_op_closure_constant(a: int) -> float:
    return a + x["a"]
"""


def test_op_versioning_closure_dict_simple(strict_op_saving):
    x = {"a": 5, "b": 10}

    @weave.op()
    def versioned_op_closure_constant(a: int) -> float:
        return a + x["a"]

    with weave.local_client():
        ref = weave.publish(versioned_op_closure_constant)
    assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

    with ref.artifact.open("obj.py") as f:
        saved_code = f.read()

    print("SAVED CODE")
    print(saved_code)

    assert saved_code == EXPECTED_CLOSURE_CONTANT_DICT_OP_CODE


EXPECTED_CLOSURE_CONTANT_DICT_NP_OP_CODE = """import weave

x = {
    "a": 5,
    "b": weave.storage.artifact_path_ref('x/b').get()
}

@weave.op()
def versioned_op_closure_constant(a: int) -> float:
    return a + x["b"].mean() + x["a"]
"""


def test_op_versioning_closure_dict_np(strict_op_saving, eager_mode):
    x = {"a": 5, "b": np.array([1, 2, 3])}

    @weave.op()
    def versioned_op_closure_constant(a: int) -> float:
        return a + x["b"].mean() + x["a"]

    ref = weave.obj_ref(versioned_op_closure_constant)
    assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

    with ref.artifact.open("obj.py") as f:
        saved_code = f.read()

    print("SAVED CODE")
    print(saved_code)

    assert saved_code == EXPECTED_CLOSURE_CONTANT_DICT_NP_OP_CODE
    op2 = weave.ref(str(ref)).get()
    assert op2(1) == 8


EXPECTED_CLOSURE_CONTANT_DICT_OPS_OP_CODE = """import weave

x = {
    "a": weave.ref('local-artifact:///op-cat:5588512188219faae386/obj').get(),
    "b": weave.ref('local-artifact:///op-dog:b8e5d369eea85c8d0852/obj').get(),
    "c": weave.ref('local-artifact:///op-dog:b8e5d369eea85c8d0852/obj').get()
}

@weave.op()
def pony(v: int):
    v = x["a"](v)
    v = x["b"](v)
    v = x["c"](v)
    print("hello from pony()")
    return v + 99
"""


def test_op_versioning_closure_dict_ops(strict_op_saving, eager_mode):
    with weave.local_client():

        @weave.op()
        def cat(v: int):
            print("hello from cat()")
            return v + 1

        @weave.op()
        def dog(v: int):
            print("hello from dog()")
            return v - 1

        x = {"a": cat, "b": dog, "c": dog}

        @weave.op()
        def pony(v: int):
            v = x["a"](v)
            v = x["b"](v)
            v = x["c"](v)
            print("hello from pony()")
            return v + 99

        ref = weave.obj_ref(pony)
        print("REF", ref)
        assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

        with ref.artifact.open("obj.py") as f:
            saved_code = f.read()

        print("SAVED CODE")
        print(saved_code)

        assert saved_code == EXPECTED_CLOSURE_CONTANT_DICT_OPS_OP_CODE
        op2 = weave.ref(str(ref)).get()
        assert op2(1) == 99


EXPECTED_MIXED_OP_CODE = """import weave
import numpy as np

dog = weave.ref('local-artifact:///op-dog:b8e5d369eea85c8d0852/obj').get()

x = {
    "a": weave.ref('local-artifact:///op-cat:5588512188219faae386/obj').get(),
    "b": weave.storage.artifact_path_ref('x/b').get()
}

@weave.op()
def pony(v: int):
    v = dog(v)
    v = x["a"](v) + x["b"].mean()
    v = np.array([v, v, v]).mean()

    print("hello from pony()")
    return v + 99
"""


def test_op_versioning_mixed(strict_op_saving, eager_mode):
    with weave.local_client():

        @weave.op()
        def cat(v: int):
            print("hello from cat()")
            return v + 1

        @weave.op()
        def dog(v: int):
            print("hello from dog()")
            return v - 1

        x = {"a": cat, "b": np.array([1, 2, 3])}

        @weave.op()
        def pony(v: int):
            v = dog(v)
            v = x["a"](v) + x["b"].mean()
            v = np.array([v, v, v]).mean()

            print("hello from pony()")
            return v + 99

        ref = weave.obj_ref(pony)
        print("REF", ref)
        assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

        with ref.artifact.open("obj.py") as f:
            saved_code = f.read()

        print("SAVED CODE")
        print(saved_code)

        assert saved_code == EXPECTED_MIXED_OP_CODE
        op2 = weave.ref(str(ref)).get()
        assert op2(1) == 102.0


def test_op_versioning_exception(strict_op_saving):
    # Just ensure this doesn't raise by running it.
    @weave.op()
    def versioned_op_exception(a: int) -> float:
        try:
            x = 1 / 0
        except Exception as e:
            print("E", e)
            return 9999
        return x


def test_op_versioning_2ops(strict_op_saving):
    with weave.local_client():

        @weave.op()
        def dog():
            print("hello from dog()")

        @weave.op()
        def cat():
            print("hello from cat()")
            dog()
            dog()

        cat()

        ref = weave.obj_ref(cat)
        assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

        with ref.artifact.open("obj.py") as f:
            saved_code = f.read()


@pytest.mark.skip("not working yet")
def test_op_return_weave_obj(strict_op_saving):
    with weave.local_client():

        @weave.type()
        class SomeObj:
            val: int

        @weave.op()
        def some_obj(v: int):
            return SomeObj(v)

        ref = weave.obj_ref(some_obj)
        assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

        with ref.artifact.open("obj.py") as f:
            saved_code = f.read()
        print("SAVED_CODE")
        print(saved_code)
        breakpoint()


EXPECTED_TYPEDICT_ANNO_CODE = """import weave
import typing

class SomeDict(typing.TypedDict):
    val: int

@weave.op()
def some_d(v: int) -> SomeDict:
    return SomeDict(val=v)
"""


def test_op_return_typeddict_annotation():
    with weave.local_client():

        class SomeDict(typing.TypedDict):
            val: int

        @weave.op()
        def some_d(v: int) -> SomeDict:
            return SomeDict(val=v)

        assert some_d(1) == {"val": 1}

        ref = weave.obj_ref(some_d)
        assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

        with ref.artifact.open("obj.py") as f:
            saved_code = f.read()
        print("SAVED_CODE")
        print(saved_code)

        assert saved_code == EXPECTED_TYPEDICT_ANNO_CODE

        op2 = weave.ref(str(ref)).get()
        assert op2(2) == {"val": 2}
