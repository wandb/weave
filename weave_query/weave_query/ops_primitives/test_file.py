import weave_query as weave

from weave_query.weave_query import file_local2


def test_file_browsing():
    test_dir = weave.weave_query.ops.local_path("./testdata/").path("test_dir")
    assert test_dir.type == file_local2.LocalDirType()
    assert weave.use(test_dir.path("b.txt").contents()) == "howdy\n"
