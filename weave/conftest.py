import os

from . import context

import pytest


def pytest_sessionstart(session):
    context.disable_analytics()


@pytest.fixture()
def fresh_server_logfile():
    def _clearlog():
        try:
            os.remove(f"/tmp/weave/log/{os.getpid()}.log")
        except (OSError, FileNotFoundError):
            pass

    _clearlog()
    yield
    _clearlog()
