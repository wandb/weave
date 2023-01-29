import pytest
from .. import filesystem
from .. import errors


def test_filesystem_access():
    fs = filesystem.Filesystem("./testdata")
    assert fs.exists("spring-lamb.jpg")
    with pytest.raises(errors.WeaveAccessDeniedError):
        fs.exists("../spring-lamb.jpg")
    with pytest.raises(errors.WeaveAccessDeniedError):
        fs.exists("///spring-lamb.jpg")
    with pytest.raises(errors.WeaveAccessDeniedError):
        fs.exists("test_dir/../../weave")
