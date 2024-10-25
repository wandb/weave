import pytest
from unittest.mock import patch, MagicMock
from weave.actions_worker.tasks import wordcount, llm_judge


@patch("weave.actions_worker.tasks.llm_judge.apply_async")
def test_action_llm_judge(mock_apply_async):
    mock_apply_async.return_value = MagicMock()
    mock_publish_results = patch("weave.actions_worker.tasks.publish_results_as_feedback").start()
    mock_ack_on_clickhouse = patch("weave.actions_worker.tasks.ack_on_clickhouse").start()

    ctx = {
        "call_id": "1",
        "project_id": "1",
        "id": "1",
    }
    out = llm_judge(ctx, "junk_payload", "junk_prompt")
    mock_publish_results.assert_called_once_with(
        ctx,
        {"llm_judge": "I'm sorry Hal, I'm afraid I can't do that."}
    )
    mock_ack_on_clickhouse.assert_called_once_with(
        ctx,
        True
    )
    # Assert that the function returned the expected output
    assert out == "I'm sorry Hal, I'm afraid I can't do that."


@patch("weave.actions_worker.tasks.wordcount.apply_async")
def test_action_wordcount(mock_apply_async):
    mock_apply_async.return_value = MagicMock()
    mock_publish_results = patch("weave.actions_worker.tasks.publish_results_as_feedback").start()
    mock_ack_on_clickhouse = patch("weave.actions_worker.tasks.ack_on_clickhouse").start()

    ctx = {
        "call_id": "1",
        "project_id": "1",
        "id": "1",
    }
    out = wordcount(ctx, "this is a test")
    mock_publish_results.assert_called_once_with(
        ctx,
        {"wordcount": 4}
    )
    mock_ack_on_clickhouse.assert_called_once_with(
        ctx,
        True
    )
    # Assert that the function returned the expected output
    assert out == 4
