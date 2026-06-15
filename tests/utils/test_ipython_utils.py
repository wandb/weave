import sys
from typing import ClassVar

import pytest

from weave.utils import ipython as ipy


def test_is_running_interactively(monkeypatch):
    """False when IPython is absent, True when a get_ipython shell is present."""
    monkeypatch.delitem(sys.modules, "IPython", raising=False)
    assert ipy.is_running_interactively() is False

    sentinel = object()
    monkeypatch.setattr(ipy, "_lazy_get_ipython", lambda: sentinel)
    assert ipy.is_running_interactively() is True


def test_get_notebook_source(monkeypatch):
    """Raises outside an interactive env, otherwise joins the shell's `In` cells."""
    monkeypatch.delitem(sys.modules, "IPython", raising=False)
    with pytest.raises(ipy.NotInteractiveEnvironmentError):
        ipy.get_notebook_source()

    class DummyShell:
        user_ns: ClassVar[dict[str, list[str]]] = {"In": ["", "a = 1", "", "b = 2"]}

    monkeypatch.setattr(ipy, "_lazy_get_ipython", lambda: DummyShell())
    assert ipy.get_notebook_source() == "a = 1\n\nb = 2"
