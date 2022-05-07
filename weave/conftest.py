import os

from . import context
from . import weave_server
from .artifacts_local import LOCAL_ARTIFACT_DIR

import pytest
import shutil


def pytest_sessionstart(session):
    context.disable_analytics()


@pytest.fixture(autouse=True)
def pre_post_each_test():
    try:
        shutil.rmtree(LOCAL_ARTIFACT_DIR)
    except (FileNotFoundError, OSError):
        pass
    yield


@pytest.fixture()
def fresh_server_logfile():
    def _clearlog():
        try:
            os.remove(weave_server.default_log_filename)
        except (OSError, FileNotFoundError):
            pass

    _clearlog()
    yield
    _clearlog()
