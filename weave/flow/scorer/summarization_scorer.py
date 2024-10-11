from pydantic import BaseModel, Field
from typing import List
from textwrap import dedent

import weave
from weave.flow.scorer.llm_scorer import LLMScorer
from weave.flow.scorer.llm_utils import instructor_client


class EntityExtractionResponse(BaseModel):
    entities: List[str] = Field(description="A list of unique entities extracted from the text")

class SummarizationScorer(LLMScorer):
    """
    Estimates summary quality by computing the recall of entities in the model output compared to the input.
    """

    extraction_prompt: str = dedent("""
    Extract unique entities from the following text without repetition.

    Text: {text}
    Entities:
    """)
    input_column: str = Field(description="The column in the dataset that contains the input text")
    
    def extract_entities(self, text: str) -> List[str]:
        # Use LLM to extract entities
        client = instructor_client(self.client)
        prompt = self.extraction_prompt.format(text=text)
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            response_model=EntityExtractionResponse,
            model=self.model_id
        )
        entities = [e.strip().lower() for e in response.entities]
        return entities
    
    @weave.op
    def score(self, model_output: str, dataset_row: dict) -> float:
        # Extract entities
        if self.input_column not in dataset_row:
            raise ValueError(f"Answer column {self.input_column} not found in dataset_row")
        output_entities = self.extract_entities(model_output)
        input_entities = self.extract_entities(dataset_row[self.input_column])
        # Calculate recall
        if not output_entities:
            return 0.0
        matches = set(output_entities) & set(input_entities)
        recall = len(matches) / len(input_entities)
        return {"recall": recall}
    


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
        summarization_scorer = SummarizationScorer(
            client=llm_client, model_id="gpt-4o", input_column="input"
        )

        # Create your dataset of examples
        examples = [
            {"input":"Harry Potter is a wizard. He is friends with Ron Weasley. They all go to Hogwarts to learn magic. They have been doing this for years. Their enemy is Voldemort, a dark wizard who is trying to kill them.",
             "model_output":"Harry Potter, Ron Weasley, and Voldemort are wizards.",
             "relevancy_score":1}
        ]

        for example in examples:
            score = summarization_scorer.score(example["model_output"], example)
            print(f"Summarization Score: {score}")

    except Exception as e:
        print(f"Error: {e}")
