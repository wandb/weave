import sys
from typing import Any, ClassVar

import pytest

from weave.utils import ipython as ipy


def test_is_running_interactively_without_ipython(monkeypatch):
    monkeypatch.delitem(sys.modules, "IPython", raising=False)
    assert ipy.is_running_interactively() is False


def test_is_running_interactively_with_stub(monkeypatch):
    sentinel = object()

    def fake_get_ipython():
        return sentinel

    monkeypatch.setattr(ipy, "_lazy_get_ipython", fake_get_ipython)
    assert ipy.is_running_interactively() is True


def test_get_notebook_source_requires_interactive(monkeypatch):
    monkeypatch.delitem(sys.modules, "IPython", raising=False)
    with pytest.raises(ipy.NotInteractiveEnvironmentError):
        ipy.get_notebook_source()


def test_get_notebook_source_reads_cells(monkeypatch):
    class DummyShell:
        user_ns: ClassVar[dict[str, Any]] = {"In": ["", "a = 1", "", "b = 2"]}

    def fake_get_ipython():
        return DummyShell()

    monkeypatch.setattr(ipy, "_lazy_get_ipython", fake_get_ipython)
    assert ipy.get_notebook_source() == "a = 1\n\nb = 2"
