# implementing metrics from ragas: https://github.com/explodinggradients/ragas

from typing import List
from pydantic import BaseModel, Field
from textwrap import dedent

import weave
from weave.flow.scorer.llm_utils import instructor_client
from weave.flow.scorer.llm_scorer import LLMScorer
from weave.flow.scorer.similarity_score import EmbeddingSimilarityScorer

class EntityExtractionResponse(BaseModel):
    entities: List[str] = Field(description="A list of unique entities extracted from the text")

class ContextEntityRecallScorer(LLMScorer):
    """
    Estimates context recall by extracting entities from the model output 
    and the expected answer, then computes the recall.
    """

    extraction_prompt: str = dedent("""
    Extract unique entities from the following text without repetition.

    Text: {text}
    Entities:
    """)
    answer_column: str = Field(description="The column in the dataset that contains the expected answer")
    
    def extract_entities(self, text: str) -> List[str]:
        # Use LLM to extract entities
        client = instructor_client(self.client)
        prompt = self.extraction_prompt.format(text=text)
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            response_model=EntityExtractionResponse,
            model=self.model_id
        )
        # Assume entities are returned as a comma-separated list
        entities = [e.strip() for e in response.entities]
        return entities
    
    @weave.op
    def score(self, model_output: str, dataset_row: dict) -> float:
        # Extract entities
        if self.answer_column not in dataset_row:
            raise ValueError(f"Answer column {self.answer_column} not found in dataset_row")
        expected_entities = self.extract_entities(model_output)
        context_entities = self.extract_entities(dataset_row[self.answer_column])
        # Calculate recall
        if not expected_entities:
            return 0.0
        matches = set(expected_entities) & set(context_entities)
        recall = len(matches) / len(expected_entities)
        return {"recall": recall}

class RelevancyResponse(BaseModel):
    reasoning: str = Field(description="Think step by step about whether the context is relevant to the question")
    relevancy_score: int = Field(ge=0, le=1, description="The relevancy score of the context to the question (0 for not relevant, 1 for relevant)")
class ContextRelevancyScorer(LLMScorer):
    """Evaluates the relevancy of the provided context to the model output."""

    relevancy_prompt: str = dedent("""
    Given the following question and context, rate the relevancy of the context to the question on a scale from 0 to 1.

    Question: {question}
    Context: {context}
    Relevancy Score (0-1):
    """)
    context_column: str = Field(description="The column in the dataset that contains the context")

    @weave.op
    def score(self, model_output: str, dataset_row: dict) -> float:
        if self.context_column not in dataset_row:
            raise ValueError(f"Context column {self.context_column} not found in dataset_row")
        context = dataset_row[self.context_column]
        llm = instructor_client(self.client)
        prompt = self.relevancy_prompt.format(question=model_output, context=context)
        response = llm.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            response_model=RelevancyResponse,
            model=self.model_id
        )
        return {"relevancy_score": response.relevancy_score}
        
if __name__ == "__main__":
    import os

    try:
        from weave.flow.scorer.llm_utils import import_client

        # Instantiate your LLM client
        OpenAIClient = import_client("openai")
        if OpenAIClient:
            llm_client = OpenAIClient(api_key=os.environ["OPENAI_API_KEY"])
        else:
            raise ImportError("OpenAI client not available")

        # Instantiate scorers
        context_entity_recall_scorer = ContextEntityRecallScorer(
            client=llm_client, model_id="gpt-4o",
            answer_column="expected"
        )
        context_relevancy_scorer = ContextRelevancyScorer(
            client=llm_client, model_id="gpt-4o",
            context_column="context"
        )
        # Create your dataset of examples
        examples = [
            {
                "question": "What is the capital of France?",
                "expected": "Paris",
                "context": "Paris is the capital of France.",
            },
            {
                "question": "Who wrote 'To Kill a Mockingbird'?",
                "expected": "Harper Lee",
                "context": "Harper Lee is the author of 'To Kill a Mockingbird'.",
            },
            # Add more examples as needed
        ]

        for example in examples:
            model_output = {"answer": example["expected"]}  # Simulate model output
            score = context_entity_recall_scorer.score(
                model_output, example
            )
            print(f"Context Entity Recall Score: {score}")
            score = context_relevancy_scorer.score(
                model_output, example
            )
            print(f"Context Relevancy Score: {score}")
    except Exception as e:
        print(e)