import shutil

from . import api as weave
from .artifacts_local import LOCAL_ARTIFACT_DIR
from .show import _show_params


def test_print_save_val():
    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass

    data = [
        {"val": 1941, "label": "cat"},
        {"val": 2195, "label": "dog"},
    ]
    ref = weave.save(data, name="my-data")

    # converting to string should give us an expression
    assert str(ref) == 'get("my-data/d45d5e33e1fe6cdad9ea76f90cd717cd")'

    # show should use the same expression
    assert (
        str(_show_params(ref)["weave_node"])
        == 'get("my-data/d45d5e33e1fe6cdad9ea76f90cd717cd")'
    )

    versions = weave.versions(ref)
    assert len(versions) == 1
    assert str(versions[0]) == "my-data/d45d5e33e1fe6cdad9ea76f90cd717cd"

    data = [
        {"val": 1941, "label": "cat"},
        {"val": 2195, "label": "dog"},
        {"val": 19, "label": "dog"},
    ]
    ref = weave.save(data, name="my-data")

    assert str(ref) == 'get("my-data/88fdc3e0ef9724be8565a3e710f6389c")'
    assert (
        str(_show_params(ref)["weave_node"])
        == 'get("my-data/88fdc3e0ef9724be8565a3e710f6389c")'
    )

    versions = weave.versions(ref)
    assert len(versions) == 2

    # Versions are randomly ordered right now! :(
    # TODO: fix
    version_strings = [str(v) for v in versions]
    assert "my-data/88fdc3e0ef9724be8565a3e710f6389c" in version_strings
    assert "my-data/d45d5e33e1fe6cdad9ea76f90cd717cd" in version_strings


def test_save_val_ops():
    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass

    ref = weave.save(5, "my-num")
    result = (ref + 2) * 3
    assert (
        str(result)
    ) == 'get("my-num/3af13035d6c49b15d283b6b1482a7341").add(2).mult(3)'
