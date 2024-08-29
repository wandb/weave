from weave.legacy.weave import api as weave
from weave.legacy.weave import ops, storage, weave_internal


def test_autocommit(cereal_csv):
    csv = ops.local_path(cereal_csv).readcsv()
    assert weave.use(csv[-1]["type"]) == "C"  # value before set is 'C'

    ops.set(csv[-1]["type"], "XXXX")

    csv = ops.local_path(cereal_csv).readcsv()
    assert weave.use(csv[-1]["type"]) == "XXXX"

    ops.set(csv[-1]["type"], "YY")

    csv = ops.local_path(cereal_csv).readcsv()
    assert weave.use(csv[-1]["type"]) == "YY"


def test_nonconst(cereal_csv):
    csv = ops.local_path(cereal_csv).readcsv()
    assert weave.use(csv[-1]["type"]) == "C"  # value before set is 'C'
    ops.set(csv[-1]["type"], "XXXX")
    csv = ops.local_path(cereal_csv).readcsv()
    assert weave.use(csv[-1]["type"]) == "XXXX"
    ops.set(csv[-1]["type"], "YY")
    csv = ops.local_path(cereal_csv).readcsv()
    assert weave.use(csv[-1]["type"]) == "YY"


def test_mutate_with_use(cereal_csv):
    csv = ops.local_path(cereal_csv).readcsv()
    ops.set(csv[-1]["type"], "XXXX")
    assert weave.use(csv[-1]["type"]) == "XXXX"
    csv = ops.local_path(cereal_csv).readcsv()
    assert weave.use(csv[-1]["type"]) == "XXXX"


def test_mutate_artifact():
    storage.save({"a": 5, "b": 6}, "my-dict:latest")
    dict_obj = ops.get("local-artifact:///my-dict:latest/obj")
    ops.set(dict_obj["a"], 17)
    assert weave.use(dict_obj["a"]) == 17


def test_csv_saveload_type(cereal_csv):
    csv = weave.use(ops.local_path(cereal_csv).readcsv())
    ref = storage.save(csv)
    storage.get(str(ref))


def test_skips_list_indexcheckpoint(cereal_csv):
    csv = ops.local_path(cereal_csv).readcsv()
    assert weave.use(csv[-1]["type"]) == "C"  # value before set is 'C'

    row = ops.List.__getitem__(ops.list_indexCheckpoint(csv), -1)
    ops.set(row["type"], "XXXX")

    csv = ops.local_path(cereal_csv).readcsv()
    assert weave.use(csv[-1]["type"]) == "XXXX"
