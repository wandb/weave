import shutil

from .. import api as weave
from .. import artifact_util
from ..show import _show_params


def test_print_save_val():
    data = [
        {"val": 1941, "label": "cat"},
        {"val": 2195, "label": "dog"},
    ]
    ref = weave.save(data, name="my-data")
    # converting to string should give us an expression
    assert (
        str(ref)
        == 'get("local-artifact:///my-data:0ede263a967353f0ddb20f3be13bcd56/obj")'
    )

    # show should use the same expression
    assert (
        str(_show_params(ref)["weave_node"])
        == 'get("local-artifact:///my-data:0ede263a967353f0ddb20f3be13bcd56/obj")'
    )

    versions = weave.versions(ref)
    assert len(versions) == 1
    assert str(versions[0].version) == "0ede263a967353f0ddb20f3be13bcd56"

    data = [
        {"val": 1941, "label": "cat"},
        {"val": 2195, "label": "dog"},
        {"val": 19, "label": "dog"},
    ]
    ref = weave.save(data, name="my-data")

    assert (
        str(ref)
        == 'get("local-artifact:///my-data:e29ccef26ed48b2b59caf0bf28974e38/obj")'
    )
    assert (
        str(_show_params(ref)["weave_node"])
        == 'get("local-artifact:///my-data:e29ccef26ed48b2b59caf0bf28974e38/obj")'
    )

    versions = weave.versions(ref)
    assert len(versions) == 2

    version_strings = [str(v.version) for v in versions]
    assert version_strings[0] == "0ede263a967353f0ddb20f3be13bcd56"
    assert version_strings[1] == "e29ccef26ed48b2b59caf0bf28974e38"


def test_save_val_ops():
    ref = weave.save(5, "my-num")
    result = (ref + 2) * 3
    assert (
        (str(result))
        == 'get("local-artifact:///my-num:a40302fe175f87a6625464187c7f99a7/obj").add(2).mult(3)'
    )
