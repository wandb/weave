import os
from typing import Literal

import pytest

from weave.integrations.dspy.callbacks import WeaveCallback
from weave.integrations.integration_utilities import op_name_from_ref


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_dspy_predict_module(client) -> None:
    import dspy

    dspy.configure(
        lm=dspy.LM(
            "openai/gpt-4o-mini",
            cache=False,
            api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        ),
        callbacks=[WeaveCallback()],
    )
    question_answering_module = dspy.Predict("question: str -> response: str")
    response = question_answering_module(question="what is the capital of france?")
    assert "paris" in response.response.lower()

    calls = list(client.calls())
    assert len(calls) == 6

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict"
    assert "paris" in call.output["response"].lower()
    assert (
        call.inputs["self"]["signature"]["description"]
        == "Given the fields `question`, produce the fields `response`."
    )

    call = calls[3]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.LM"
    assert "paris" in call.output[0].lower()

    call = calls[4]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "litellm.completion"
    assert "paris" in call.output["choices"][0]["message"]["content"].lower()

    call = calls[5]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "openai.chat.completions.create"
    assert "paris" in call.output["choices"][0]["message"]["content"].lower()


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_dspy_chain_of_thought_module(client) -> None:
    import dspy

    dspy.configure(
        lm=dspy.LM(
            "openai/gpt-4o-mini",
            cache=False,
            api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        ),
        callbacks=[WeaveCallback()],
    )

    cot_module = dspy.ChainOfThought("question -> answer: float")
    response = cot_module(
        question="Two dice are tossed. What is the probability that the sum equals two?"
    )
    assert response.answer >= 0.027

    calls = list(client.calls())
    assert len(calls) == 7

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.ChainOfThought"
    assert response["answer"] >= 0.027

    call = calls[1]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict"
    assert response["answer"] >= 0.027
    assert (
        call.inputs["self"]["signature"]["description"]
        == "Given the fields `question`, produce the fields `answer`."
    )

    call = calls[4]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.LM"

    call = calls[5]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "litellm.completion"

    call = calls[6]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "openai.chat.completions.create"


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_dspy_classification_module(client) -> None:
    import dspy

    dspy.configure(
        lm=dspy.LM(
            "openai/gpt-4o-mini",
            cache=False,
            api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        ),
        callbacks=[WeaveCallback()],
    )

    class Classify(dspy.Signature):
        """Classify sentiment of a given sentence."""

        sentence: str = dspy.InputField()
        sentiment: Literal["positive", "negative", "neutral"] = dspy.OutputField()
        confidence: float = dspy.OutputField()

    classify = dspy.Predict(Classify)
    response = classify(
        sentence="This book was super fun to read, though not the last chapter."
    )
    assert response.sentiment == "positive"
    assert response.confidence >= 0.5

    calls = list(client.calls())
    assert len(calls) == 6

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict"
    assert response["sentiment"] == "positive"
    assert response["confidence"] >= 0.5
    assert (
        call.inputs["self"]["signature"]["description"]
        == "Classify sentiment of a given sentence."
    )

    call = calls[3]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.LM"

    call = calls[4]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "litellm.completion"

    call = calls[5]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "openai.chat.completions.create"


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_dspy_information_extraction_module(client) -> None:
    import dspy

    dspy.configure(
        lm=dspy.LM(
            "openai/gpt-4o-mini",
            cache=False,
            api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        ),
        callbacks=[WeaveCallback()],
    )

    class ExtractInfo(dspy.Signature):
        """Extract structured information from text."""

        text: str = dspy.InputField()
        title: str = dspy.OutputField()
        headings: list[str] = dspy.OutputField()
        entities: list[dict[str, str]] = dspy.OutputField(
            desc="a list of entities and their metadata"
        )

    module = dspy.Predict(ExtractInfo)

    text = (
        "Apple Inc. announced its latest iPhone 14 today."
        "The CEO, Tim Cook, highlighted its new features in a press release."
    )
    response = module(text=text)
    assert "apple" in response.title.lower()

    calls = list(client.calls())
    assert len(calls) == 6

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "dspy.Predict"
    assert "apple" in call.output["title"].lower()
    assert (
        call.inputs["self"]["signature"]["description"]
        == "Extract structured information from text."
    )


@pytest.mark.vcr(
    filter_headers=["authorization", "x-api-key"],
    allowed_hosts=["api.wandb.ai", "localhost", "trace.wandb.ai"],
)
@pytest.mark.skip_clickhouse_client
def test_dspy_multi_stage_pipeline(client) -> None:
    import dspy

    dspy.configure(
        lm=dspy.LM(
            "openai/gpt-4o-mini",
            cache=False,
            api_key=os.environ.get("OPENAI_API_KEY", "DUMMY_API_KEY"),
        ),
        callbacks=[WeaveCallback()],
    )

    class Outline(dspy.Signature):
        """Outline a thorough overview of a topic."""

        topic: str = dspy.InputField()
        title: str = dspy.OutputField()
        sections: list[str] = dspy.OutputField()
        section_subheadings: dict[str, list[str]] = dspy.OutputField(
            desc="mapping from section headings to subheadings"
        )

    class DraftSection(dspy.Signature):
        """Draft a top-level section of an article."""

        topic: str = dspy.InputField()
        section_heading: str = dspy.InputField()
        section_subheadings: list[str] = dspy.InputField()
        content: str = dspy.OutputField(desc="markdown-formatted section")

    class DraftArticle(dspy.Module):
        def __init__(self):
            self.build_outline = dspy.ChainOfThought(Outline)
            self.draft_section = dspy.ChainOfThought(DraftSection)

        def forward(self, topic):
            outline = self.build_outline(topic=topic)
            sections = []
            for heading, subheadings in outline.section_subheadings.items():
                section, subheadings = (
                    f"## {heading}",
                    [f"### {subheading}" for subheading in subheadings],
                )
                section = self.draft_section(
                    topic=outline.title,
                    section_heading=section,
                    section_subheadings=subheadings,
                )
                sections.append(section.content)
            return dspy.Prediction(title=outline.title, sections=sections)

    draft_article = DraftArticle()
    article = draft_article(topic="World Cup 2002")
    assert "world cup" in article.title.lower()

    calls = list(client.calls())
    assert len(calls) == 50

    call = calls[0]
    assert call.started_at < call.ended_at
    trace_name = op_name_from_ref(call.op_name)
    assert trace_name == "DraftArticle"
