import pytest
from .. import filesystem
from .. import errors
from .. import environment


@pytest.fixture()
def test_datafs():
    old_weave_filesystem_dir = environment.weave_filesystem_dir
    environment.weave_filesystem_dir = lambda: "./testdata"
    yield
    environment.weave_filesystem_dir = old_weave_filesystem_dir


def test_filesystem_access(test_datafs):
    fs = filesystem.Filesystem()
    assert fs.exists("spring-lamb.jpg")
    with pytest.raises(errors.WeaveAccessDeniedError):
        fs.exists("../spring-lamb.jpg")
    with pytest.raises(errors.WeaveAccessDeniedError):
        fs.exists("///spring-lamb.jpg")
    with pytest.raises(errors.WeaveAccessDeniedError):
        fs.exists("test_dir/../../weave")
