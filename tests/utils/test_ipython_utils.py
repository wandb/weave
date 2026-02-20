import sys
import types
from textwrap import dedent
from typing import Any, ClassVar

import pytest

from weave.utils import ipython as ipy


def test_lazy_get_ipython_returns_none_when_ipython_not_loaded(monkeypatch):
    monkeypatch.delitem(sys.modules, "IPython", raising=False)
    assert ipy._lazy_get_ipython() is None


def test_lazy_get_ipython_returns_none_when_ipython_not_package(monkeypatch):
    monkeypatch.setitem(sys.modules, "IPython", types.ModuleType("IPython"))
    monkeypatch.delitem(sys.modules, "IPython.core", raising=False)
    monkeypatch.delitem(sys.modules, "IPython.core.getipython", raising=False)
    assert ipy._lazy_get_ipython() is None


def test_lazy_get_ipython_returns_shell_when_get_ipython_available(monkeypatch):
    sentinel_shell = object()

    ipython_pkg = types.ModuleType("IPython")
    ipython_pkg.__path__ = []  # Mark as package for submodule imports.
    core_pkg = types.ModuleType("IPython.core")
    core_pkg.__path__ = []
    getipython_module = types.ModuleType("IPython.core.getipython")
    getipython_module.get_ipython = lambda: sentinel_shell

    monkeypatch.setitem(sys.modules, "IPython", ipython_pkg)
    monkeypatch.setitem(sys.modules, "IPython.core", core_pkg)
    monkeypatch.setitem(sys.modules, "IPython.core.getipython", getipython_module)

    assert ipy._lazy_get_ipython() is sentinel_shell


@pytest.mark.parametrize("shell, expected", [(None, False), (object(), True)])
def test_is_running_interactively(monkeypatch, shell, expected):
    monkeypatch.setattr(ipy, "_lazy_get_ipython", lambda: shell)
    assert ipy.is_running_interactively() is expected


def test_get_notebook_source_requires_interactive(monkeypatch):
    monkeypatch.setattr(ipy, "_lazy_get_ipython", lambda: None)
    with pytest.raises(ipy.NotInteractiveEnvironmentError):
        ipy.get_notebook_source()


def test_get_notebook_source_requires_user_namespace(monkeypatch):
    class DummyShell:
        pass

    monkeypatch.setattr(ipy, "_lazy_get_ipython", lambda: DummyShell())
    with pytest.raises(AttributeError, match="Cannot access user namespace"):
        ipy.get_notebook_source()


def test_get_notebook_source_reads_cells(monkeypatch):
    class DummyShell:
        user_ns: ClassVar[dict[str, Any]] = {"In": ["", "a = 1", "", "b = 2", None]}

    monkeypatch.setattr(ipy, "_lazy_get_ipython", lambda: DummyShell())
    assert ipy.get_notebook_source() == "a = 1\n\nb = 2"


def test_get_class_source_returns_latest_class_definition(monkeypatch):
    class SampleClass:
        pass

    notebook_source = dedent(
        """
        class SampleClass:
            value = 1

        class AnotherClass:
            pass

        class SampleClass:
            value = 2
        """
    ).strip()

    monkeypatch.setattr(ipy, "get_notebook_source", lambda: notebook_source)

    class_source = ipy.get_class_source(SampleClass)
    assert "class SampleClass:" in class_source
    assert "value = 2" in class_source
    assert "value = 1" not in class_source


def test_get_class_source_raises_when_class_missing(monkeypatch):
    class MissingClass:
        pass

    notebook_source = "class AnotherClass:\n    pass\n"
    monkeypatch.setattr(ipy, "get_notebook_source", lambda: notebook_source)

    with pytest.raises(
        ipy.ClassNotFoundError,
        match="Class 'MissingClass' not found in the notebook",
    ):
        ipy.get_class_source(MissingClass)
