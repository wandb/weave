import importlib
import json
import os
import subprocess
import sys
import warnings

import pytest

import weave
import weave.shared
from weave.trace import (
    constants,
    errors,
    otel_context_keys,
    otel_span_attrs,
    refs_base,
    refs_internal,
    server_tracing,
    trace_server_converter,
)
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
    query,
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
    "weave.shared.constants": constants,
    "weave.shared.refs": refs_base,
    "weave.shared.refs_internal": refs_internal,
    "weave.shared.trace_server_converter": trace_server_converter,
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


# The weave.shared API type modules. The client sends plain dicts and reads the
# generated client's types, so they warn without naming a replacement.
_TYPE_MODULES = [
    "weave.shared.agents.constants",
    "weave.shared.agents.schema",
    "weave.shared.agents.semconv",
    "weave.shared.agents.types",
    "weave.shared.common_interface",
    "weave.shared.http_service_interface",
    "weave.shared.interface.query",
    "weave.shared.sensitive_data.policy",
    "weave.shared.service_interface",
    "weave.shared.trace_server_interface",
    "weave.shared.trace_server_interface_util",
    "weave.shared.validation",
    "weave.shared.validation_util",
]

# Their weave.trace_server aliases.
_TYPE_MODULE_ALIASES = [
    "weave.trace_server.agents.constants",
    "weave.trace_server.agents.semconv",
    "weave.trace_server.agents.types",
    "weave.trace_server.common_interface",
    "weave.trace_server.http_service_interface",
    "weave.trace_server.interface.feedback_types",
    "weave.trace_server.interface.query",
    "weave.trace_server.sensitive_data.policy",
    "weave.trace_server.service_interface",
    "weave.trace_server.trace_server_interface",
    "weave.trace_server.validation",
    "weave.trace_server.validation_util",
]

_FEEDBACK_TYPES = "weave.shared.interface.feedback_types"


def _expected_type_module_warning(name: str) -> str:
    if name == _FEEDBACK_TYPES:
        return (
            f"{name} is deprecated and will be removed in a future release; import "
            "the feedback type names and selectors from weave.trace.feedback_types "
            "instead."
        )
    if name.startswith("weave.trace_server."):
        return (
            f"{name} is deprecated since weave 0.53.13 and will be removed in a "
            "future release."
        )
    return f"{name} is deprecated and will be removed in a future release."


# Imports each module after forgetting every weave.shared and weave.trace_server
# module, so the modules it imports load again too.
_COLD_IMPORT = """
import importlib, json, sys, warnings
import weave

def forget():
    for name in [n for n in sys.modules if n.startswith(("weave.shared.", "weave.trace_server."))]:
        module = sys.modules.pop(name)
        parent = sys.modules.get(name.rpartition(".")[0])
        if parent is not None and vars(parent).get(name.rpartition(".")[2]) is module:
            del vars(parent)[name.rpartition(".")[2]]

warnings_by_module = {}
for name in sys.argv[1:]:
    forget()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        importlib.import_module(name)
    warnings_by_module[name] = [
        str(w.message) for w in caught if issubclass(w.category, FutureWarning)
    ]
print(json.dumps(warnings_by_module))
"""


def test_type_modules_and_their_aliases_warn_once_when_imported_cold() -> None:
    names = [*_TYPE_MODULES, _FEEDBACK_TYPES, *_TYPE_MODULE_ALIASES]
    result = subprocess.run(
        [sys.executable, "-c", _COLD_IMPORT, *names],
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(result.stdout.splitlines()[-1]) == {
        name: [_expected_type_module_warning(name)] for name in names
    }


def test_type_modules_warn_once_on_access_and_point_at_the_caller() -> None:
    # A fresh interpreter: `import weave` no longer loads these modules.
    code = (
        "import json, warnings\n"
        "import weave\n"
        "with warnings.catch_warnings(record=True) as caught:\n"
        "    warnings.simplefilter('always')\n"
        "    weave.shared.sensitive_data.policy\n"
        "    weave.shared.interface.query\n"
        "    from weave.shared.interface import feedback_types\n"
        "    weave.shared.agents.semconv\n"
        "    weave.shared.validation_util\n"
        "    from weave.shared import common_interface\n"
        "    weave.shared.trace_server_interface\n"
        "    weave.shared.trace_server_interface\n"
        "print(json.dumps([(str(w.message), w.filename) for w in caught\n"
        "    if issubclass(w.category, FutureWarning)]))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )

    assert json.loads(result.stdout.splitlines()[-1]) == [
        [_expected_type_module_warning(name), "<string>"]
        for name in [
            "weave.shared.sensitive_data.policy",
            "weave.shared.interface.query",
            _FEEDBACK_TYPES,
            "weave.shared.agents.semconv",
            "weave.shared.validation_util",
            "weave.shared.common_interface",
            "weave.shared.trace_server_interface",
        ]
    ]


def test_import_weave_loads_no_type_module() -> None:
    code = (
        "import json, sys\n"
        "import weave, weave.durability.wal_sender\n"
        "print(json.dumps(sorted(name for name in sys.modules\n"
        "    if name.startswith(('weave.shared.', 'weave.trace_server.'))\n"
        "    or name.endswith('.remote_http_trace_server'))))\n"
    )
    result = subprocess.run(
        [sys.executable, "-W", "error::FutureWarning", "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )

    assert json.loads(result.stdout.splitlines()[-1]) == []


# What `weave.init` builds by default, driven over a mock transport: an op call,
# a calls and a feedback query, and a saved view with a query.
_DEFAULT_CLIENT = """
import json, sys
import httpx
import weave
from weave.trace import weave_init
from weave.trace.context import weave_client_context
from weave.trace.weave_client import WeaveClient
from weave.trace_server_bindings.caching_middleware_trace_server import (
    CachingMiddlewareTraceServer,
)
from weave.vendor.weave_server_sdk import Client as StainlessClient
from weave.wandb_interface.auth import ApiKeyCredentials

paths = set()

def handle(request):
    paths.add(request.url.path)
    if request.url.path.endswith("/stream_query"):
        return httpx.Response(200, headers={"content-type": "application/jsonl"})
    return httpx.Response(200, json={"id": "i", "trace_id": "t", "digest": "d",
        "result": [], "total_count": 0})

server = weave_init.init_weave_get_server(ApiKeyCredentials("k" * 40))
server._stainless_client = StainlessClient(
    base_url="http://weave.test", username="", password="",
    http_client=httpx.Client(transport=httpx.MockTransport(handle)),
)
weave_init._get_server_info(server)
client = WeaveClient(
    "e", "p", CachingMiddlewareTraceServer.from_env(server), ensure_project_exists=False
)
weave_client_context.set_weave_client_global(client)

@weave.op
def add(a, b):
    return a + b

add(1, 2)
[call for call in client.get_calls()]
[feedback for feedback in client.get_feedback()]
weave.publish(weave.SavedView().add_filter("inputs.a", ">", 1), name="view")
client.finish()
print(json.dumps({
    "server": type(server).__name__,
    "paths": sorted(paths),
    "loaded": sorted(name for name in sys.modules
        if name.startswith(("weave.shared.", "weave.trace_server."))
        or name.endswith(".remote_http_trace_server")),
}))
"""


def test_default_client_loads_no_type_module(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, "-W", "error::FutureWarning", "-c", _DEFAULT_CLIENT],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "WEAVE_SERVER_CACHE_DIR": str(tmp_path)},
        timeout=120,
    )

    assert json.loads(result.stdout.splitlines()[-1]) == {
        "server": "StainlessRemoteHTTPTraceServer",
        "paths": [
            "/calls/stream_query",
            "/feedback/query",
            "/file/create",
            "/obj/create",
            "/server_info",
            "/v2/e/p/calls/complete",
        ],
        "loaded": [],
    }


def test_shared_query_and_runtime_models_are_the_clients() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        from weave.shared import common_interface, trace_server_interface
        from weave.shared.interface import query as shared_query

    assert shared_query.Query is query.Query
    assert shared_query.EqOperation is query.EqOperation
    assert trace_server_interface.Query is query.Query
    assert trace_server_interface.CallsFilter is query.CallsFilter
    assert common_interface.SortBy is trace_server_interface.SortBy is query.SortBy
    assert trace_server_interface.CustomRuntimeID is weave.CustomRuntimeID
    assert trace_server_interface.TraceStatus is constants.TraceStatus


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


# The error classes that moved from weave.shared.errors to weave.trace.errors.
_MOVED_ERROR_CLASSES = [
    "BadQueryParameterError",
    "CallsCompleteModeRequired",
    "DigestMismatchError",
    "Error",
    "ErrorCode",
    "InsertTooLarge",
    "InvalidExternalRef",
    "InvalidFieldError",
    "InvalidIdFormat",
    "InvalidRequest",
    "LightweightUpdateNotAllowedError",
    "MissingLLMApiKeyError",
    "NotFoundError",
    "ObjectDeletedError",
    "ObjectNameTypeCollision",
    "ProjectNotFound",
    "QueryEstimatedTimeoutExceededError",
    "QueryIllegalTypeofArgumentError",
    "QueryMemoryLimitExceededError",
    "QueryNoCommonTypeError",
    "QueryTimeoutExceededError",
    "RefObjectsNotFoundError",
    "RequestTooLarge",
    "RunNotFound",
]

_SHARED_ERRORS_WARNING = (
    "weave.shared.errors is deprecated and will be removed in a future release; "
    "import the error classes from weave.trace.errors instead."
)


@pytest.mark.parametrize("access", ["import", "attribute"])
def test_shared_errors_warns_once_and_reexports_the_moved_classes(
    access: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delitem(sys.modules, "weave.shared.errors", raising=False)
    monkeypatch.delitem(vars(weave.shared), "errors", raising=False)
    with warnings.catch_warnings(record=True) as record:
        warnings.simplefilter("always")
        if access == "import":
            shared_errors = importlib.import_module("weave.shared.errors")
        else:
            shared_errors = weave.shared.errors

    assert _future_warnings(record) == [_SHARED_ERRORS_WARNING]
    if access == "attribute":
        # The warning points at the caller, not at importlib.
        future = [w for w in record if issubclass(w.category, FutureWarning)]
        assert future[0].filename == __file__
    assert all(
        getattr(shared_errors, name) is getattr(errors, name)
        for name in _MOVED_ERROR_CLASSES
    )
