from __future__ import annotations

from types import ModuleType

from weave.integrations.anthropic import anthropic_sdk
from weave.integrations.integration_utilities import op_name_from_call
from weave.trace.op import is_op


def test_beta_messages_parse_autopatched(client, monkeypatch) -> None:
    class Messages:
        def create(self, *args, **kwargs):
            return {"type": "create"}

        def stream(self, *args, **kwargs):
            return iter(())

    class AsyncMessages:
        async def create(self, *args, **kwargs):
            return {"type": "create"}

        async def stream(self, *args, **kwargs):
            return iter(())

    class BetaMessages(Messages):
        def parse(self, *args, **kwargs):
            return {"parsed": kwargs.get("value")}

    class BetaAsyncMessages(AsyncMessages):
        async def parse(self, *args, **kwargs):
            return {"parsed": kwargs.get("value")}

    messages_module = ModuleType("anthropic.resources.messages")
    messages_module.Messages = Messages
    messages_module.AsyncMessages = AsyncMessages

    beta_messages_module = ModuleType("anthropic.resources.beta.messages")
    beta_messages_module.Messages = BetaMessages
    beta_messages_module.AsyncMessages = BetaAsyncMessages

    def fake_import_module(name: str):
        if name == "anthropic.resources.messages":
            return messages_module
        if name == "anthropic.resources.beta.messages":
            return beta_messages_module
        raise ImportError(name)

    monkeypatch.setattr(anthropic_sdk, "_anthropic_patcher", None)
    monkeypatch.setattr(anthropic_sdk.importlib, "import_module", fake_import_module)

    patcher = anthropic_sdk.get_anthropic_patcher()
    assert patcher.attempt_patch()

    assert is_op(beta_messages_module.Messages.parse)
    assert is_op(beta_messages_module.AsyncMessages.parse)

    result = beta_messages_module.Messages().parse(value="ok")
    assert result == {"parsed": "ok"}

    calls = list(client.get_calls())
    assert len(calls) == 1
    assert op_name_from_call(calls[0]) == "anthropic.beta.Messages.parse"
    assert calls[0].output == {"parsed": "ok"}
