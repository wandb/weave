from hashlib import sha256

from .. import api

from .. import ops
from .. import api as weave

import pytest


def test_dir():
    testdir = ops.local_path("testdata/test_dir")
    # TODO: causes test to fail because of serialization mutatio

    size = api.use(testdir.size())
    assert size == 111
    dir = api.use(testdir)
    assert len(dir.dirs) == 1
    assert len(dir.dirs["sub_dir"].dirs) == 0
    assert len(dir.dirs["sub_dir"].files) == 1
    assert len(dir.files) == 2


def test_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        ops.local_path("fake_file_.idontexist")


def test_wbartifact_file_table():
    proj = ops.project("shawn", "show-test")
    av = proj.artifactVersion("show", "v14")
    file = av.file("obj.table.json")
    table = file.table().rows()
    # assert weave.use(file.size()) == 66217
    # assert weave.use(file.path()) == "obj.table.json"
    assert weave.use(table[0]["total"]) == 46


# def test_localartifact_file_table():
#     av = ops.local_artifact_version("my-table-artifact", "xasdfj")
#     file = av.file("obj.table.json")
#     table = file.table()
#     assert table[0]["total"] == 46


# def test_localfile_table():
#     file = ops.local_path("testdata/obj.table.json")
#     table = file.table()
#     assert table[0]["total"] == 46
