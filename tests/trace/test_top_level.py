from unittest.mock import Mock

import weave
from weave.trace import api
from weave.trace.weave_client import WeaveClient


def test_get_client(client: WeaveClient):
    assert weave.get_client() is client


def test_get_client_no_client():
    assert weave.get_client() is None


def test_init_can_skip_project_creation(monkeypatch):
    expected_client = object()
    init_weave = Mock(return_value=expected_client)
    monkeypatch.setattr(api, "configure_logger", Mock())
    monkeypatch.setattr(api, "replace_settings", Mock())
    monkeypatch.setattr(api, "should_disable_weave", Mock(return_value=False))
    monkeypatch.setattr(api.weave_init, "init_weave", init_weave)

    result = weave.init("entity/existing-project", ensure_project_exists=False)

    assert result is expected_client
    init_weave.assert_called_once_with(
        "entity/existing-project",
        ensure_project_exists=False,
        postprocess_inputs=None,
        postprocess_output=None,
        attributes=None,
    )
