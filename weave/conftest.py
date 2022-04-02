import os

from . import context
from . import weave_server

import pytest


def pytest_sessionstart(session):
    context.disable_analytics()


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
