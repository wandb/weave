import pytest
import shutil

from . import ops
from . import storage
from . import api as weave
from .artifacts_local import LOCAL_ARTIFACT_DIR


def test_autocommit():
    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass
    shutil.copy("testdata/cereal.csv", "/tmp/cereal.csv")

    csv = ops.local_path("/tmp/cereal.csv").readcsv()
    assert weave.use(csv[-1]["type"]) == "C"  # value before set is 'C'

    weave.use(csv[-1]["type"].set("XXXX"))

    csv = ops.local_path("/tmp/cereal.csv").readcsv()
    assert weave.use(csv[-1]["type"]) == "XXXX"

    weave.use(csv[-1]["type"].set("YY"))

    csv = ops.local_path("/tmp/cereal.csv").readcsv()
    assert weave.use(csv[-1]["type"]) == "YY"


def test_nonconst():
    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass
    shutil.copy("testdata/cereal.csv", "/tmp/cereal.csv")

    # note, not doing a use here.
    csv = ops.local_path("/tmp/cereal.csv").readcsv()
    assert weave.use(csv[-1]["type"]) == "C"  # value before set is 'C'
    weave.use(csv[-1]["type"].set("XXXX"))
    # cache.RESULT_CACHE.clear()
    csv = ops.local_path("/tmp/cereal.csv").readcsv()
    assert weave.use(csv[-1]["type"]) == "XXXX"
    weave.use(csv[-1]["type"].set("YY"))
    # cache.RESULT_CACHE.clear()
    csv = ops.local_path("/tmp/cereal.csv").readcsv()
    assert weave.use(csv[-1]["type"]) == "YY"


def test_mutate_with_use():
    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass
    shutil.copy("testdata/cereal.csv", "/tmp/cereal.csv")

    csv = ops.local_path("/tmp/cereal.csv").readcsv()
    weave.use(csv[-1]["type"].set("XXXX"))
    assert weave.use(csv[-1]["type"]) == "XXXX"
    csv = ops.local_path("/tmp/cereal.csv").readcsv()
    assert weave.use(csv[-1]["type"]) == "XXXX"


def test_mutate_artifact():
    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass
    storage.save({"a": 5, "b": 6}, "my-dict")
    dict_obj = ops.get("my-dict/latest")
    weave.use(dict_obj["a"].set(17))
    assert weave.use(dict_obj["a"]) == 17


def test_csv_saveload_type():
    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except FileNotFoundError:
        pass
    shutil.copy("testdata/cereal.csv", "/tmp/cereal.csv")
    csv = weave.use(ops.local_path("/tmp/cereal.csv").readcsv())
    assert isinstance(csv, ops.Csv)
    ref = storage.save(csv)
    new_csv = storage.get(str(ref))
    assert isinstance(new_csv, ops.Csv)
