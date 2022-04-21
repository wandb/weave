from .ecosystem import async_demo
from . import compile
from .artifacts_local import LOCAL_ARTIFACT_DIR


def test_automatic_await_compile():
    import shutil

    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass

    twelve = async_demo.slowmult(3, 4, 0.01)
    twenty_four = async_demo.slowmult(2, twelve, 0.01)
    result = compile.compile([twenty_four])
    assert str(result[0]) == "2.slowmult(slowmult(3, 4, 0.01).await(), 0.01)"
