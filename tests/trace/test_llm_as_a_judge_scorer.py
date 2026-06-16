from unittest.mock import patch

import pytest

import weave
from tests.trace.util import FAKE_NOT_IMPLEMENTED
from weave.flow.scorer import Scorer
from weave.prompt.prompt import MessagesPrompt
from weave.scorers import LLMAsAJudgeScorer
from weave.trace.object_record import pydantic_object_record
from weave.trace.refs import ObjectRef
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.interface.builtin_object_classes.builtin_object_registry import (
    LLMStructuredCompletionModel,
)
from weave.trace_server.interface.builtin_object_classes.llm_structured_model import (
    LLMStructuredCompletionModelDefaultParams,
)


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_publish_and_load_scorer_with_prompt_ref(weave_active):
    """Test that LLMAsAJudgeScorer with a MessagesPrompt ref can be published and loaded.

    When the scorer is loaded via weave.get(), the scoring_prompt ref string
    is automatically resolved to the actual MessagesPrompt object.
    """
    # Create and publish a MessagesPrompt
    prompt = MessagesPrompt(
        messages=[
            {
                "role": "user",
                "content": "Inputs: {inputs}. Output: {output}. Is this correct?",
            }
        ]
    )
    prompt_ref = weave.publish(prompt)
    prompt_uri = str(prompt_ref.uri)

    # Create scorer with prompt URI string
    scorer = LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                response_format="json_object",
            ),
        ),
        scoring_prompt=prompt_uri,
    )
    assert scorer.scoring_prompt == prompt_uri

    # Publish and retrieve - ref should be resolved
    scorer_ref = weave.publish(scorer)
    loaded_scorer = weave.get(scorer_ref.uri)

    assert isinstance(loaded_scorer, LLMAsAJudgeScorer)
    assert isinstance(loaded_scorer.scoring_prompt, MessagesPrompt)
    assert len(loaded_scorer.scoring_prompt.messages) == 1


def test_score_with_string_prompt():
    """Test score() with a simple string prompt."""
    scorer = LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                response_format="json_object",
            ),
        ),
        scoring_prompt="Output: {output}",
    )

    mock_result = {"score": 1.0}
    with patch.object(
        LLMStructuredCompletionModel, "predict", return_value=mock_result
    ) as mock_predict:
        result = scorer.score(output="hello")

        assert result == mock_result
        mock_predict.assert_called_once()
        messages = mock_predict.call_args[0][0]
        assert messages == [{"role": "user", "content": "Output: hello"}]


def test_score_with_messages_prompt():
    """Test score() with a MessagesPrompt and template variables."""
    prompt = MessagesPrompt(
        messages=[
            {"role": "system", "content": "You are a {judge_type} judge."},
            {"role": "user", "content": "Expected: {expected}, Got: {output}"},
        ]
    )

    scorer = LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                response_format="json_object",
            ),
        ),
        scoring_prompt=prompt,
    )

    mock_result = {"score": 0.95}
    with patch.object(
        LLMStructuredCompletionModel, "predict", return_value=mock_result
    ) as mock_predict:
        result = scorer.score(output="4", expected="4", judge_type="math")

        assert result == mock_result
        mock_predict.assert_called_once()
        messages = mock_predict.call_args[0][0]
        assert len(messages) == 2
        assert messages[0]["content"] == "You are a math judge."
        assert messages[1]["content"] == "Expected: 4, Got: 4"


def _make_judge_scorer() -> LLMAsAJudgeScorer:
    return LLMAsAJudgeScorer(
        model=LLMStructuredCompletionModel(
            llm_model_id="gpt-4o-mini",
            default_params=LLMStructuredCompletionModelDefaultParams(
                response_format="json_object",
            ),
        ),
        scoring_prompt="Output: {output}",
    )


def test_llm_as_a_judge_scorer_record_excludes_op_methods():
    """WB-35184: the scorer and its nested model must not record their @op methods.

    Publishing those embeds CustomWeaveType(Op) payloads that the scoring worker
    rejects (``_assert_safe_scorer_payload``), so a programmatically created judge
    monitor silently never scores. Both classes opt out via
    ``_weave_exclude_ops_from_record``; a plain Scorer subclass still records its ops.
    """
    scorer = _make_judge_scorer()

    scorer_record = pydantic_object_record(scorer)
    assert "score" not in scorer_record.__dict__
    assert "summarize" not in scorer_record.__dict__
    assert scorer_record._class_name == "LLMAsAJudgeScorer"

    model_record = pydantic_object_record(scorer.model)
    assert "predict" not in model_record.__dict__
    assert model_record._class_name == "LLMStructuredCompletionModel"

    class _PlainScorer(Scorer):
        pass

    plain_record = pydantic_object_record(_PlainScorer(name="plain"))
    assert "score" in plain_record.__dict__
    assert "summarize" in plain_record.__dict__


@pytest.mark.skipif(FAKE_NOT_IMPLEMENTED, reason="fake: not implemented yet")
def test_llm_as_a_judge_scorer_publish_has_no_op_refs(client):
    """The published payload must carry no op refs, so the scoring worker accepts it.

    The worker walks the payload, follows refs, and fails closed on any nested
    CustomWeaveType(Op). Previously the scorer's score/summarize and the nested
    model's predict serialized as op refs and tripped that guard (WB-35184).
    """
    scorer = _make_judge_scorer()
    ref = weave.publish(scorer)

    def stored_val(name: str, digest: str) -> dict:
        res = client.server.obj_read(
            tsi.ObjReadReq(project_id=client.project_id, object_id=name, digest=digest)
        )
        return res.obj.val

    scorer_val = stored_val(ref.name, ref.digest)
    assert "score" not in scorer_val
    assert "summarize" not in scorer_val

    # The nested model is published as its own ref; resolve and check it too.
    model_ref = ObjectRef.parse_uri(scorer_val["model"])
    model_val = stored_val(model_ref.name, model_ref.digest)
    assert "predict" not in model_val

    # The scorer still round-trips back to a usable object.
    loaded = weave.get(ref.uri)
    assert isinstance(loaded, LLMAsAJudgeScorer)
    assert isinstance(loaded.model, LLMStructuredCompletionModel)
