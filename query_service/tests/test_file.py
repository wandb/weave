import pytest

import weave
from weave.legacy.weave import api, context_state, environment, errors, ops


def test_dir():
    testdir = ops.local_path("testdata/test_dir")
    # TODO: causes test to fail because of serialization mutatio

    size = api.use(testdir.size)
    assert size == 111
    dir = api.use(testdir)
    assert len(dir.dirs) == 1
    assert len(dir.dirs["sub_dir"].dirs) == 0
    assert len(dir.dirs["sub_dir"].files) == 1
    assert len(dir.files) == 2


def test_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        ops.local_path("fake_file_.idontexist")
