from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest

from weave.chat.inference_models import InferenceModels
from weave.chat.types.models import ModelsResponseError, ModelsResponseSuccess
from weave.trace_server.constants import INFERENCE_HOST


def _make_models() -> InferenceModels:
    client = SimpleNamespace(entity="my-entity", project="my-project")
    return InferenceModels(client)


def _patch_httpx(response: MagicMock) -> MagicMock:
    """Patch httpx.Client so the context manager yields a mock whose GET/POST
    return ``response``. Returns the mock client for call assertions.
    """
    mock_client = MagicMock()
    mock_client.get.return_value = response
    mock_client.post.return_value = response
    ctx = MagicMock()
    ctx.__enter__.return_value = mock_client
    return mock_client, ctx


def test_list_success_uses_get_and_sorts() -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "object": "list",
        "data": [
            {"id": "b-model", "object": "model", "owned_by": "wandb"},
            {"id": "a-model", "object": "model", "owned_by": "wandb"},
        ],
    }
    mock_client, ctx = _patch_httpx(response)

    with (
        patch(
            "weave.chat.inference_models.get_wandb_api_context",
            return_value="fake-key",
        ),
        patch("weave.chat.inference_models.httpx.Client", return_value=ctx),
    ):
        result = _make_models().list()

    # The fix under test: a GET request is issued (not POST).
    expected_url = f"https://{INFERENCE_HOST}/v1/models"
    expected_headers = {
        "Authorization": "Bearer fake-key",
        "OpenAI-Project": "my-entity/my-project",
        "Content-Type": "application/json",
    }
    mock_client.get.assert_called_once_with(expected_url, headers=expected_headers)
    mock_client.post.assert_not_called()

    assert isinstance(result, ModelsResponseSuccess)
    assert [m.id for m in result.data] == ["a-model", "b-model"]


def test_list_missing_api_key_raises() -> None:
    with patch("weave.chat.inference_models.get_wandb_api_context", return_value=None):
        with pytest.raises(ValueError, match="No API key found"):
            _make_models().list()


def test_list_401_raises_http_status_error() -> None:
    response = MagicMock()
    response.status_code = 401
    response.reason_phrase = "Unauthorized"
    response.request = MagicMock()
    _, ctx = _patch_httpx(response)

    with (
        patch(
            "weave.chat.inference_models.get_wandb_api_context",
            return_value="fake-key",
        ),
        patch("weave.chat.inference_models.httpx.Client", return_value=ctx),
    ):
        with pytest.raises(httpx.HTTPStatusError, match="my-entity"):
            _make_models().list()


def test_list_non_200_returns_error_model() -> None:
    response = MagicMock()
    response.status_code = 500
    response.json.return_value = {
        "error": {
            "code": "internal_error",
            "message": "boom",
            "type": "server_error",
        }
    }
    _, ctx = _patch_httpx(response)

    with (
        patch(
            "weave.chat.inference_models.get_wandb_api_context",
            return_value="fake-key",
        ),
        patch("weave.chat.inference_models.httpx.Client", return_value=ctx),
    ):
        result = _make_models().list()

    assert isinstance(result, ModelsResponseError)
    assert result.error.message == "boom"
