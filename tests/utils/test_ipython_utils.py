import sys
import types

import pytest

from weave.utils import ipython as ipy


def test_is_running_interactively_without_ipython(monkeypatch):
    monkeypatch.delitem(sys.modules, "IPython", raising=False)
    assert ipy.is_running_interactively() is False


def test_is_running_interactively_with_stub(monkeypatch):
    module = types.ModuleType("IPython")
    module.get_ipython = lambda: object()
    monkeypatch.setitem(sys.modules, "IPython", module)
    assert ipy.is_running_interactively() is True


def test_get_notebook_source_requires_interactive(monkeypatch):
    monkeypatch.delitem(sys.modules, "IPython", raising=False)
    with pytest.raises(ipy.NotInteractiveEnvironmentError):
        ipy.get_notebook_source()


def test_get_notebook_source_reads_cells(monkeypatch):
    module = types.ModuleType("IPython")

    class DummyShell:
        user_ns = {"In": ["", "a = 1", "", "b = 2"]}

    module.get_ipython = lambda: DummyShell()
    monkeypatch.setitem(sys.modules, "IPython", module)
    assert ipy.get_notebook_source() == "a = 1\n\nb = 2"
