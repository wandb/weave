import weave_query as weave
import weave_query
from weave_query.ops_primitives import file_local


def test_file_browsing():
    test_dir = weave_query.ops.local_path("./testdata/").path("test_dir")
    assert test_dir.type == file_local.LocalDirType()
    assert weave.use(test_dir.path("b.txt").contents()) == "howdy\n"
