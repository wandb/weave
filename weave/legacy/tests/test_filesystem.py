import asyncio

import pytest

from weave.legacy.weave import environment, errors, filesystem


@pytest.fixture()
def test_datafs():
    legacy_filesystem_dir = environment.weave_filesystem_dir
    environment.weave_filesystem_dir = lambda: "./testdata"
    yield
    environment.weave_filesystem_dir = legacy_filesystem_dir


def test_filesystem_access(test_datafs):
    fs = filesystem.Filesystem()
    assert fs.exists("spring-lamb.jpg")
    with pytest.raises(errors.WeaveAccessDeniedError):
        fs.exists("../spring-lamb.jpg")
    with pytest.raises(errors.WeaveAccessDeniedError):
        fs.exists("///spring-lamb.jpg")
    with pytest.raises(errors.WeaveAccessDeniedError):
        fs.exists("test_dir/../../weave")


@pytest.mark.asyncio()
async def test_filesystem_updates_atime_on_read(enable_touch_on_read, test_datafs):
    filename = "spring-lamb.jpg"
    fs = filesystem.FilesystemAsync()
    old_atime = (await fs.stat(filename)).st_atime
    async with fs.open_read(filename):
        await asyncio.sleep(0.5)  # give the spawned task time to execute
        new_atime = (await fs.stat(filename)).st_atime
    assert new_atime > old_atime

    fs = filesystem.Filesystem()
    old_atime = fs.stat(filename).st_atime
    with fs.open_read(filename):
        new_atime = fs.stat(filename).st_atime
    assert new_atime > old_atime
