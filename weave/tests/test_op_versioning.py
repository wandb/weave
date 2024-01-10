import pytest
import shutil
from .. import api as weave
from .. import artifact_fs
from .. import op_def
from .. import derive_op
import numpy as np


def test_op_versioning():
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


EXPECTED_SOLO_OP_CODE = """import typing
import weave


import numpy as np
import weave as weave
@weave.op()
def solo_versioned_op(a: int) -> float:
    # Rely on the "import numpy as np" import
    return np.array([a, a]).mean()
"""


def test_solo_op_versioning(strict_op_saving):
    from . import op_versioning_solo

    ref = weave.obj_ref(op_versioning_solo.solo_versioned_op)
    assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

    with ref.artifact.open("obj.py") as f:
        saved_code = f.read()

    assert saved_code == EXPECTED_SOLO_OP_CODE


EXPECTED_OBJECT_OP_CODE = """import typing
import weave


import numpy as np
import weave as weave
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

    assert saved_code == EXPECTED_OBJECT_OP_CODE


EXPECTED_IMPORTFROM_OP_CODE = """import typing
import weave


from numpy import array
import weave as weave
@weave.op()
def versioned_op_importfrom(a: int) -> float:
    return array([x + 1 for x in range(a)]).mean()
"""


def test_op_versioning_importfrom(strict_op_saving):
    from . import op_versioning_importfrom

    ref = weave.obj_ref(op_versioning_importfrom.versioned_op_importfrom)
    assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

    with ref.artifact.open("obj.py") as f:
        saved_code = f.read()

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


EXPECTED_CLOSURE_CONTANT_OP_CODE = """import typing
import weave


x = 10
import weave.api as weave
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
    assert isinstance(ref, artifact_fs.FilesystemArtifactRef)

    with ref.artifact.open("obj.py") as f:
        saved_code = f.read()

    assert saved_code == EXPECTED_CLOSURE_CONTANT_OP_CODE
