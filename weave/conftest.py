import os
import tempfile

from . import context

import pytest


def pytest_sessionstart(session):
    context.disable_analytics()


@pytest.fixture()
def isolated_filesystem():
    cwd = os.getcwd()
    tmpdir = tempfile.mkdtemp()
    os.chdir(tmpdir)
    yield
    os.chdir(cwd)
