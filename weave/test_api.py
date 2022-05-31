import shutil

from . import api as weave
from . import artifacts_local
from .show import _show_params


def test_print_save_val():
    try:
        shutil.rmtree(artifacts_local.LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass

    data = [
        {"val": 1941, "label": "cat"},
        {"val": 2195, "label": "dog"},
    ]
    ref = weave.save(data, name="my-data")
    # converting to string should give us an expression
    assert (
        str(ref)
        == 'get("local-artifact:///tmp/local-artifacts/my-data/d45d5e33e1fe6cdad9ea76f90cd717cd")'
    )

    # show should use the same expression
    assert (
        str(_show_params(ref)["weave_node"])
        == 'get("local-artifact:///tmp/local-artifacts/my-data/d45d5e33e1fe6cdad9ea76f90cd717cd")'
    )

    versions = weave.versions(ref)
    assert len(versions) == 1
    assert str(versions[0].version) == "d45d5e33e1fe6cdad9ea76f90cd717cd"

    data = [
        {"val": 1941, "label": "cat"},
        {"val": 2195, "label": "dog"},
        {"val": 19, "label": "dog"},
    ]
    ref = weave.save(data, name="my-data")

    assert (
        str(ref)
        == 'get("local-artifact:///tmp/local-artifacts/my-data/88fdc3e0ef9724be8565a3e710f6389c")'
    )
    assert (
        str(_show_params(ref)["weave_node"])
        == 'get("local-artifact:///tmp/local-artifacts/my-data/88fdc3e0ef9724be8565a3e710f6389c")'
    )

    versions = weave.versions(ref)
    assert len(versions) == 2

    version_strings = [str(v.version) for v in versions]
    assert version_strings[0] == "d45d5e33e1fe6cdad9ea76f90cd717cd"
    assert version_strings[1] == "88fdc3e0ef9724be8565a3e710f6389c"


def test_save_val_ops():
    try:
        shutil.rmtree(artifacts_local.LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass

    ref = weave.save(5, "my-num")
    result = (ref + 2) * 3
    assert (
        (str(result))
        == 'get("local-artifact:///tmp/local-artifacts/my-num/3af13035d6c49b15d283b6b1482a7341").add(2).mult(3)'
    )
