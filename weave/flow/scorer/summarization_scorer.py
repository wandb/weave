from pydantic import BaseModel, Field
from typing import List
from textwrap import dedent

import weave
from weave.flow.scorer.llm_scorer import InstructorLLMScorer
from weave.flow.scorer.llm_utils import create


class EntityExtractionResponse(BaseModel):
    entities: List[str] = Field(description="A list of unique entities extracted from the text")

class SummarizationScorer(InstructorLLMScorer):
    """
    Estimates summary quality by computing the recall of entities in the model output compared to the input.
    """

    extraction_prompt: str = dedent("""
    Extract unique entities from the following text without repetition.

    Text: {text}
    Entities:
    """)

    temperature: float = 0.7
    max_tokens: int = 1024
    
    def extract_entities(self, text: str) -> List[str]:
        # Use LLM to extract entities
        prompt = self.extraction_prompt.format(text=text)
        response = create(
            self.client,
            messages=[{"role": "user", "content": prompt}],
            response_model=EntityExtractionResponse,
            model=self.model_id,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        entities = [e.strip().lower() for e in response.entities]
        return entities
    
    @weave.op
    def score(self, input: str, output: str, **kwargs) -> float:
        # Extract entities
        output_entities = self.extract_entities(output)
        input_entities = self.extract_entities(input)
        # Calculate recall
        if not output_entities:
            return 0.0
        matches = set(output_entities) & set(input_entities)
        recall = len(matches) / len(input_entities)
        return {"recall": recall}
    


if __name__ == "__main__":
    import os, asyncio

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
            client=llm_client, model_id="gpt-4o", column_map={"text": "input"}
        )

        @weave.op
        def f(summary: str): 
            return summary

        # Create your dataset of examples
        examples = [
            {"text":"Harry Potter is a wizard. He is friends with Ron Weasley. They all go to Hogwarts to learn magic. They have been doing this for years. Their enemy is Voldemort, a dark wizard who is trying to kill them.",
             "summary":"Harry Potter, Ron Weasley, and Voldemort are wizards.",
             "relevancy_score":1},
        ]
        evaluation = weave.Evaluation(dataset=examples, scorers=[summarization_scorer])
        asyncio.run(evaluation.evaluate(f))

        # good naming:
        def summarization_scorer2(text: str, output: str):
            scorer =  SummarizationScorer(client=llm_client, model_id="gpt-4o")
            return scorer.score(input=text, output=output)

        evaluation = weave.Evaluation(dataset=examples, scorers=[summarization_scorer2])
        asyncio.run(evaluation.evaluate(f))


    except Exception as e:
        print(f"Error: {e}")
