import shutil

from weave.legacy.weave import api as weave

from ...legacy.weave.show import _show_params


def test_print_save_val():
    data = [
        {"val": 1941, "label": "cat"},
        {"val": 2195, "label": "dog"},
    ]
    ref = weave.save(data, name="my-data")
    # converting to string should give us an expression
    assert str(ref) == 'get("local-artifact:///my-data:latest/obj")'

    # show should use the same expression
    show_params = _show_params(ref)
    assert (
        str(show_params["weave_node"])
        == 'get("local-artifact:///dashboard-my-data:latest/obj")'
    )
    panel = weave.use(show_params["weave_node"])
    assert (
        str(panel.config.items["my-data"])
        == 'get("local-artifact:///my-data:latest/obj")'
    )

    versions = weave.versions(ref)
    assert len(versions) == 1
    assert str(versions[0].version) == "0ede263a967353f0ddb2"

    data = [
        {"val": 1941, "label": "cat"},
        {"val": 2195, "label": "dog"},
        {"val": 19, "label": "dog"},
    ]
    ref = weave.save(data, name="my-data")

    assert str(ref) == 'get("local-artifact:///my-data:latest/obj")'
    show_params = _show_params(ref)
    assert (
        str(show_params["weave_node"])
        == 'get("local-artifact:///dashboard-my-data:latest/obj")'
    )
    panel = weave.use(show_params["weave_node"])
    assert (
        str(panel.config.items["my-data"])
        == 'get("local-artifact:///my-data:latest/obj")'
    )

    versions = weave.versions(ref)
    assert len(versions) == 2

    version_strings = [str(v.version) for v in versions]
    assert version_strings[0] == "0ede263a967353f0ddb2"
    assert version_strings[1] == "e29ccef26ed48b2b59ca"


def test_save_val_ops():
    ref = weave.save(5, "my-num")
    result = (ref + 2) * 3
    assert (str(result)) == 'get("local-artifact:///my-num:latest/obj").add(2).mult(3)'
