from . import context


def pytest_sessionstart(session):
    context.disable_analytics()
