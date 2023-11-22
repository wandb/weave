# import pytest
# from openai.types.chat.chat_completion import ChatCompletion, Choice
# from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
# from openai.types.completion_usage import CompletionUsage

# from weave.monitoring.openai.interface import CombinedChoice


# @pytest.mark.parametrize(
#     "initial_combined, delta, expected_result",
#     [
#         # Test case 1
#         (CombinedChoice(content="initial", role="admin"), Choice(delta=Delta(content=" update", role="user")), CombinedChoice(content="initial update", role="admin")),
#         # Test case 2
#         (CombinedChoice(), Choice(delta=Delta(content="new", function_call="func_call")), CombinedChoice(content="new", function_call="func_call")),
#         # Add more test cases as needed
#     ],
# )
# def test_update_combined_choice(initial_combined, delta, expected_result):
#     result = update_combined_choice(initial_combined, delta)
#     assert result.dict() == expected_result.dict()
