import importlib
import pkgutil
import sys

import pytest

import weave.trace_server
from weave.shared import (
    common_interface,
    http_service_interface,
    service_interface,
    trace_server_converter,
    trace_server_interface,
    validation,
)
from weave.shared.agents import constants, semconv
from weave.shared.agents import types as agent_types
from weave.shared.helpers import url_safety
from weave.shared.interface import feedback_types
from weave.shared.sensitive_data import policy
from weave.trace_server import common_interface as common_interface_legacy
from weave.trace_server import http_service_interface as http_service_interface_legacy
from weave.trace_server import service_interface as service_interface_legacy
from weave.trace_server import trace_server_converter as trace_server_converter_legacy
from weave.trace_server import trace_server_interface as trace_server_interface_legacy
from weave.trace_server import validation as validation_legacy
from weave.trace_server.agents import constants as constants_legacy
from weave.trace_server.agents import semconv as semconv_legacy
from weave.trace_server.agents import types as agent_types_legacy
from weave.trace_server.helpers import url_safety as url_safety_legacy
from weave.trace_server.interface import feedback_types as feedback_types_legacy
from weave.trace_server.sensitive_data import policy as policy_legacy

pytestmark = pytest.mark.trace_server


def test_trace_server_paths_are_the_shared_modules() -> None:
    assert trace_server_interface is trace_server_interface_legacy
    assert common_interface is common_interface_legacy
    assert service_interface is service_interface_legacy
    assert http_service_interface is http_service_interface_legacy
    assert trace_server_converter is trace_server_converter_legacy
    assert validation is validation_legacy
    assert agent_types is agent_types_legacy
    assert semconv is semconv_legacy
    assert constants is constants_legacy
    assert feedback_types is feedback_types_legacy
    assert policy is policy_legacy
    assert url_safety is url_safety_legacy


def _trace_server_modules() -> list[str]:
    return [
        info.name
        for info in pkgutil.walk_packages(
            weave.trace_server.__path__, "weave.trace_server."
        )
        if not info.ispkg
    ]


@pytest.mark.parametrize("name", _trace_server_modules())
def test_trace_server_paths_warn_with_the_new_path(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delitem(sys.modules, name, raising=False)
    new_name = name.replace("weave.trace_server", "weave.shared", 1)
    with pytest.warns(FutureWarning) as record:
        importlib.import_module(name)
    assert [str(w.message) for w in record] == [
        f"{name} is deprecated since weave 0.53.13 and will be removed after "
        f"weave 0.53.13; import {new_name} instead."
    ]
