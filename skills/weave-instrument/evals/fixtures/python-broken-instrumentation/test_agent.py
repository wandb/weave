from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agent import AgentResult, TraceSettings, handle_turn


@pytest.mark.asyncio
@patch("agent.patch_openai")
@patch("agent.weave.init")
async def test_weave_wiring(
    init: MagicMock,
    patcher: MagicMock,
) -> None:
    runner = AsyncMock()
    runner.run.return_value = AgentResult(output="done", state="completed")
    settings = TraceSettings(
        project="my-team/support-agent",
        tracing_api_key="test-key",
        sharing_with_wandb_allowed=False,
    )

    result = await handle_turn("hello", runner, settings)

    assert result == AgentResult(output="done", state="completed")
    init.assert_called_once()
    patcher.assert_called_once()
