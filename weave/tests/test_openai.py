from unittest.mock import MagicMock

import pytest

from weave.monitoring2.openai.patch import AsyncChatCompletions


@pytest.mark.asyncio
async def test_base_create_method():
    # Arrange
    base_create = MagicMock()
    callbacks = []
    async_chat_completions = AsyncChatCompletions(base_create, callbacks)
    args = (1, 2, 3)
    kwargs = {"param1": "value1", "param2": "value2"}

    # Act
    result = await async_chat_completions.create(*args, **kwargs)

    # Assert
    base_create.assert_called_once_with(*args, **kwargs)
    assert result == base_create.return_value
