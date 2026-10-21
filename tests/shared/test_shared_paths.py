import importlib
import json
import subprocess
import sys
import warnings

import pytest

import weave.shared
from weave.trace import otel_context_keys, otel_span_attrs, server_tracing
from weave.trace.serialization import digest, object_class_util
from weave.utils import ids, pydantic_util

pytestmark = pytest.mark.trace_server

_MOVED_MODULES = {
    "weave.shared.ids": ids,
    "weave.shared.otel_span_attrs": otel_span_attrs,
    "weave.shared.otel_context_keys": otel_context_keys,
    "weave.shared.tracing": server_tracing,
    "weave.shared.pydantic_util": pydantic_util,
    "weave.shared.digest": digest,
    "weave.shared.object_class_util": object_class_util,
}


def _future_warnings(record: list[warnings.WarningMessage]) -> list[str]:
    """The FutureWarning messages; garbage collection can add unrelated warnings."""
    return [str(w.message) for w in record if issubclass(w.category, FutureWarning)]


def _expected_module_warning(name: str) -> str:
    return (
        f"{name} is deprecated and will be removed in a future release; "
        f"import {_MOVED_MODULES[name].__name__} instead."
    )


def _expected_name_warning(name: str) -> str:
    return (
        f"weave.shared.{name} is deprecated and will be removed in a future "
        "release; import it from weave.trace.serialization.digest instead."
    )


@pytest.fixture
def fresh_shared(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forget every moved name, so the next lookup goes through the alias again.

    It edits the package's `__dict__`: `delattr` would look the name up first, and
    the lookup itself imports the alias.
    """
    for name in _MOVED_MODULES:
        monkeypatch.delitem(sys.modules, name, raising=False)
        monkeypatch.delitem(vars(weave.shared), name.rsplit(".", 1)[1], raising=False)
    for name in weave.shared.__all__:
        monkeypatch.delitem(vars(weave.shared), name, raising=False)


@pytest.mark.parametrize("name", sorted(_MOVED_MODULES))
def test_shared_paths_warn_and_are_the_new_modules(
    name: str, fresh_shared: None
) -> None:
    with pytest.warns(FutureWarning) as record:
        module = importlib.import_module(name)

    assert module is _MOVED_MODULES[name]
    assert _future_warnings(record) == [_expected_module_warning(name)]


@pytest.mark.parametrize("name", sorted(_MOVED_MODULES))
def test_shared_attributes_warn_and_are_the_new_modules(
    name: str, fresh_shared: None
) -> None:
    with pytest.warns(FutureWarning) as record:
        module = getattr(weave.shared, name.rsplit(".", 1)[1])

    assert module is _MOVED_MODULES[name]
    assert _future_warnings(record) == [_expected_module_warning(name)]


def test_shared_attribute_then_import_warns_once(fresh_shared: None) -> None:
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        by_attribute = weave.shared.ids
        by_import = importlib.import_module("weave.shared.ids")

    assert by_attribute is by_import is ids
    assert _future_warnings(record) == [_expected_module_warning("weave.shared.ids")]


@pytest.mark.parametrize("name", sorted(weave.shared.__all__))
def test_shared_package_digest_names_warn_once(name: str, fresh_shared: None) -> None:
    namespace: dict[str, object] = {}
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        exec(f"from weave.shared import {name} as value", namespace)

    assert namespace["value"] is getattr(digest, name)
    assert _future_warnings(record) == [_expected_name_warning(name)]


def test_shared_star_import_binds_the_digest_names(fresh_shared: None) -> None:
    namespace: dict[str, object] = {}
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        exec("from weave.shared import *", namespace)

    assert {name: namespace[name] for name in weave.shared.__all__} == {
        name: getattr(digest, name) for name in weave.shared.__all__
    }
    assert _future_warnings(record) == [
        _expected_name_warning(name) for name in weave.shared.__all__
    ]


def test_import_weave_warns_about_no_moved_module() -> None:
    code = (
        "import json, warnings\n"
        "with warnings.catch_warnings(record=True) as caught:\n"
        "    warnings.simplefilter('always')\n"
        "    import weave\n"
        "print(json.dumps([str(w.message) for w in caught"
        " if str(w.message).startswith(('weave.shared', 'weave.trace_server'))]))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert json.loads(result.stdout.splitlines()[-1]) == []
