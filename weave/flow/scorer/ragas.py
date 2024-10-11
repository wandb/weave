# implememting metrics from ragas: https://github.com/explodinggradients/ragas

from typing import Any, List

from weave.flow.scorer.lightllm import LLMFactory
from weave.flow.scorer.llm_scorer import EmbeddingSimilarityScorer, LLMScorer


class ContextEntityRecallScorer(LLMScorer):
    """
    Estimates context recall by extracting entities from the expected answer and
    the provided context, then computes the recall.
    """

    extraction_prompt: str = """
    Extract unique entities from the following text without repetition.

    Text: {text}
    Entities:
    """

    def extract_entities(self, text: str) -> List[str]:
        # Use LLM to extract entities
        llm = LLMFactory.create(self.client, self.model)
        prompt = self.extraction_prompt.format(text=text)
        response = llm.chat(messages=[{"role": "user", "content": prompt}])
        # Assume entities are returned as a comma-separated list
        entities = [e.strip() for e in response.split(",")]
        return entities

    def score(self, model_output: Any, expected: str, context: str) -> float:
        # Extract entities
        expected_entities = self.extract_entities(expected)
        context_entities = self.extract_entities(context)
        # Calculate recall
        if not expected_entities:
            return 0.0
        matches = set(expected_entities) & set(context_entities)
        recall = len(matches) / len(expected_entities)
        return recall


class ContextRelevancyScorer(LLMScorer):
    """Evaluates the relevancy of the provided context to the input question."""

    relevancy_prompt: str = """
    Given the following question and context, rate the relevancy of the context to the question on a scale from 0 to 1.

    Question: {question}
    Context: {context}
    Relevancy Score (0-1):
    """

    def score(self, model_output: Any, input_text: str, context: str) -> float:
        llm = LLMFactory.create(self.client, self.model)
        prompt = self.relevancy_prompt.format(question=input_text, context=context)
        response = llm.chat(messages=[{"role": "user", "content": prompt}])
        # Parse the response to get the relevancy score
        try:
            score = float(response.strip())
            return max(0.0, min(score, 1.0))  # Ensure the score is between 0 and 1
        except ValueError:
            return 0.0  # Return 0 if parsing fails


class ContextPrecisionScorer(LLMScorer):
    """Determines whether the provided context was useful in arriving at the given answer."""

    precision_prompt: str = """
    Given the question, answer, and context, determine if the context was useful in arriving at the answer.
    Respond with 1 if useful, 0 if not.

    Question: {question}
    Answer: {answer}
    Context: {context}
    Verdict (1 for useful, 0 for not useful):
    """

    def score(
        self, model_output: Any, input_text: str, expected: str, context: str
    ) -> float:
        llm = LLMFactory.create(self.client, self.model)
        prompt = self.precision_prompt.format(
            question=input_text, answer=expected, context=context
        )
        response = llm.chat(messages=[{"role": "user", "content": prompt}])
        # Parse the response to get the verdict
        try:
            verdict = int(response.strip())
            return float(verdict)
        except ValueError:
            return 0.0  # Return 0 if parsing fails


class FaithfulnessScorer(LLMScorer):
    """Measures the factual consistency of the generated answer against the provided context."""

    faithfulness_prompt: str = """
    Compare the following answer and context for factual consistency. Rate the faithfulness on a scale from 0 to 1.

    Answer: {answer}
    Context: {context}
    Faithfulness Score (0-1):
    """

    def score(self, model_output: Any, expected: str, context: str) -> float:
        llm = LLMFactory.create(self.client, self.model)
        answer = model_output.get("answer", "")
        prompt = self.faithfulness_prompt.format(answer=answer, context=context)
        response = llm.chat(messages=[{"role": "user", "content": prompt}])
        # Parse the response to get the faithfulness score
        try:
            score = float(response.strip())
            return max(0.0, min(score, 1.0))
        except ValueError:
            return 0.0  # Return 0 if parsing fails


class AnswerSimilarityScorer(EmbeddingSimilarityScorer):
    """Measures the similarity between the generated answer and the expected answer."""

    def score(self, model_output: Any, expected: str) -> float:
        generated_answer = model_output.get("answer", "")
        return super().score(generated_answer, expected)


from typing import Any

from weave.flow.scorer.llm_scorer import LLMScorer


class AnswerCorrectnessScorer(LLMScorer):
    """Evaluates the correctness of the answer based on the ground truth."""

    correctness_prompt: str = """
    Given the question, generated answer, and ground truth, rate the correctness of the answer on a scale from 0 to 1.

    Question: {question}
    Generated Answer: {generated_answer}
    Ground Truth: {ground_truth}
    Correctness Score (0-1):
    """

    def score(self, model_output: Any, input_text: str, expected: str) -> float:
        llm = LLMFactory.create(self.client, self.model)
        generated_answer = model_output.get("answer", "")
        prompt = self.correctness_prompt.format(
            question=input_text,
            generated_answer=generated_answer,
            ground_truth=expected,
        )
        response = llm.chat(messages=[{"role": "user", "content": prompt}])
        # Parse the response to get the correctness score
        try:
            score = float(response.strip())
            return max(0.0, min(score, 1.0))
        except ValueError:
            return 0.0  # Return 0 if parsing fails


if __name__ == "__main__":
    import os
    import weave
    try:
        from weave.flow.scorer.lightllm import import_client

        # Instantiate your LLM client
        OpenAIClient = import_client("openai")
        if OpenAIClient:
            llm_client = OpenAIClient(api_key=os.environ["OPENAI_API_KEY"])  # Replace with your API key
        else:
            raise ImportError("OpenAI client not available")

        # Instantiate scorers
        context_entity_recall_scorer = ContextEntityRecallScorer(
            client=llm_client, model="gpt-4o"
        )
        context_relevancy_scorer = ContextRelevancyScorer(client=llm_client, model="gpt-4")
        context_precision_scorer = ContextPrecisionScorer(client=llm_client, model="gpt-4")
        faithfulness_scorer = FaithfulnessScorer(client=llm_client, model="gpt-4")
        answer_similarity_scorer = AnswerSimilarityScorer(
            client=llm_client, model="text-embedding-ada-002"
        )
        answer_correctness_scorer = AnswerCorrectnessScorer(
            client=llm_client, model="gpt-4o"
        )

        # Create your dataset of examples
        examples = [
            {"question": "What is the capital of France?", "expected": "Paris", "context": "Paris is the capital of France."},
            {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee", "context": "Harper Lee is the author of 'To Kill a Mockingbird'."},
            # Add more examples as needed
        ]

        scorers = [
            context_entity_recall_scorer,
            context_relevancy_scorer,
            context_precision_scorer,
            faithfulness_scorer,
            answer_similarity_scorer,
            answer_correctness_scorer,
        ]

        for example in examples:
            model_output = {"answer": example["expected"]}  # Simulate model output
            for scorer in scorers:
                if isinstance(scorer, ContextEntityRecallScorer):
                    score = scorer.score(model_output, example["expected"], example["context"])
                elif isinstance(scorer, ContextRelevancyScorer):
                    score = scorer.score(model_output, example["question"], example["context"])
                elif isinstance(scorer, ContextPrecisionScorer):
                    score = scorer.score(model_output, example["question"], example["expected"], example["context"])
                elif isinstance(scorer, FaithfulnessScorer):
                    score = scorer.score(model_output, example["expected"], example["context"])
                elif isinstance(scorer, AnswerSimilarityScorer):
                    score = scorer.score(model_output, example["expected"])
                elif isinstance(scorer, AnswerCorrectnessScorer):
                    score = scorer.score(model_output, example["question"], example["expected"])
                print(f"{scorer.__class__.__name__} score for '{example['question']}': {score}")
    except Exception as e:
        print(e)