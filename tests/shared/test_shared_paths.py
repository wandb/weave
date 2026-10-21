import importlib
import json
import subprocess
import sys
import warnings

import pytest

import weave.shared
from weave.trace import otel_context_keys, otel_span_attrs, server_tracing
from weave.trace.builtin_object_classes import (
    agent_dashboard,
    alert_spec,
    annotation_spec,
    base_object_def,
    builtin_object_registry,
    comparison_view,
    leaderboard,
    llm_structured_model,
    provider,
    saved_view,
    test_only_example,
)
from weave.trace.serialization import (
    digest,
    object_class_util,
    serialization_metadata,
)
from weave.utils import ids, pydantic_util, url_safety

pytestmark = pytest.mark.trace_server

_MOVED_MODULES = {
    "weave.shared.ids": ids,
    "weave.shared.otel_span_attrs": otel_span_attrs,
    "weave.shared.otel_context_keys": otel_context_keys,
    "weave.shared.tracing": server_tracing,
    "weave.shared.pydantic_util": pydantic_util,
    "weave.shared.digest": digest,
    "weave.shared.object_class_util": object_class_util,
    "weave.shared.serialization_metadata": serialization_metadata,
    "weave.shared.helpers.url_safety": url_safety,
    "weave.shared.interface.builtin_object_classes.agent_dashboard": agent_dashboard,
    "weave.shared.interface.builtin_object_classes.alert_spec": alert_spec,
    "weave.shared.interface.builtin_object_classes.annotation_spec": annotation_spec,
    "weave.shared.interface.builtin_object_classes.base_object_def": base_object_def,
    "weave.shared.interface.builtin_object_classes.builtin_object_registry": builtin_object_registry,
    "weave.shared.interface.builtin_object_classes.comparison_view": comparison_view,
    "weave.shared.interface.builtin_object_classes.leaderboard": leaderboard,
    "weave.shared.interface.builtin_object_classes.llm_structured_model": llm_structured_model,
    "weave.shared.interface.builtin_object_classes.provider": provider,
    "weave.shared.interface.builtin_object_classes.saved_view": saved_view,
    "weave.shared.interface.builtin_object_classes.test_only_example": test_only_example,
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
        parent, attribute = name.rsplit(".", 1)
        monkeypatch.delitem(sys.modules, name, raising=False)
        monkeypatch.delitem(
            vars(importlib.import_module(parent)), attribute, raising=False
        )
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
    parent, attribute = name.rsplit(".", 1)
    package = importlib.import_module(parent)
    with pytest.warns(FutureWarning) as record:
        module = getattr(package, attribute)

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


def test_shared_subpackages_resolve_their_moved_modules_on_access() -> None:
    # A fresh interpreter: `import weave` no longer loads these subpackages.
    code = (
        "import json, warnings\n"
        "import weave\n"
        "with warnings.catch_warnings(record=True) as caught:\n"
        "    warnings.simplefilter('always')\n"
        "    weave.shared.helpers.url_safety\n"
        "    weave.shared.interface.builtin_object_classes.leaderboard\n"
        "print(json.dumps([str(w.message) for w in caught]))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert json.loads(result.stdout.splitlines()[-1]) == [
        _expected_module_warning("weave.shared.helpers.url_safety"),
        _expected_module_warning(
            "weave.shared.interface.builtin_object_classes.leaderboard"
        ),
    ]


@pytest.mark.parametrize(
    "package",
    ["weave.shared.interface.builtin_object_classes", "weave.shared.helpers"],
)
def test_emptied_packages_star_import_the_moved_modules(
    package: str, fresh_shared: None
) -> None:
    names = importlib.import_module(package).__all__
    namespace: dict[str, object] = {}
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        exec(f"from {package} import *", namespace)

    assert {name: namespace[name] for name in names} == {
        name: _MOVED_MODULES[f"{package}.{name}"] for name in names
    }
    assert _future_warnings(record) == [
        _expected_module_warning(f"{package}.{name}") for name in names
    ]
