---
sidebar_position: 0
hide_table_of_contents: true
---

# Building an Evaluation Pipeline

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/wandb/weave/blob/master/docs/docs/guides/cookbooks/llamaindex_rag_ncert/notebooks/04_evaluation.ipynb)

To iterate on any AI application, we need a way to systematically evaluate its performace to check if it's improving or not. To do so, a common practice is to test it against the same set of examples when there is a change. In this recipe, we will build an evaluation pipeline to evaluate the responses of our AI assistant using [`weave.Evaluation`](https://wandb.github.io/weave/guides/core-types/evaluations) which is a flexible API that provides us with a first-class way to track evaluations.

## Building an Evaluation Dataset

We build an evaluation dataset by scraping a question bank of solved question-answer pairs of the Flamigo textbook from [LearnCBSE](https://www.learncbse.in/chapter-wise-important-questions-class-12-english/). The dataset consists of 358 question-answer pairs corresponding to the 8 chapters from our knowledge base in the following format:

```python
{
  "question": "What was the mood in the classroom when M. Hamel gave his last French lesson? ",
  "answer": "When M.Hamel was giving his last French ; lesson, the mood in the classroom was solemn and sombre. When he announced that this was their last French lesson everyone present in the classroom suddenly developed patriotic feelings for their native language and genuinely regretted ignoring their mother tongue.",
  "marks": "3-4",
  "chapter_name": "The Last Lesson"
}
```

:::note

Check out [this notebook](https://colab.research.google.com/github/wandb/weave/blob/master/docs/docs/guides/cookbooks/llamaindex_rag_ncert/notebooks/02_fetch_question_banks.ipynb) for the code to scrape the dataset and publish it on Weave.

:::

We log this dataset as a [`weave.Dataset`](../../core-types/datasets.md) which enables us to collect examples for evaluation and automatically track versions for accurate comparisons.

```python
# We scrape the data in a list of dictionaries, where each dictionary consists
# of the same consistent schema as mentioned above. This data structure
# serves as the rows of the dataset.
question_bank = [
    {
        "question": "What was the mood in the classroom when M. Hamel gave his last French lesson? ",
        "answer": "When M.Hamel was giving his last French ; lesson, the mood in the classroom was solemn and sombre. When he announced that this was their last French lesson everyone present in the classroom suddenly developed patriotic feelings for their native language and genuinely regretted ignoring their mother tongue.",
        "marks": "3-4",
        "chapter_name": "The Last Lesson"
    },
    ...
]

# Create the weave dataset
dataset = weave.Dataset(
    name="flamingos-prose-question-bank", rows=question_bank
)

# Publish the dataset
weave.publish(dataset)
```

| ![](./images/weave_evaluation_dataset.gif) |
|---|
| Exploring the evaluation dataset using the Weave UI. |

## Evaluating with an LLM Judge

One approach to evaluate an LLM application is to use another LLM as a judge to evaluate aspects of it. In this recipe, we demonstrate a simple example of using an LLM judge as a `weave.Scorer` to try to measure the correctness of the AI assistant's response by prompting it to verify if the the response is relevant to the context and how well it holds up to the ground-truth answer from the dataset.

```python
import instructor
import weave
from openai import OpenAI
from pydantic import BaseModel
from typing import Dict, Optional


# The pydantic object representing
# the LLM's judge's structure response
class JudgeResponse(BaseModel):
    marks: float
    explanation: str


# The LLM judge model
class OpenaAIJudgeModel(weave.Scorer):
    model: str = "gpt-4"
    max_retries: int = 5
    _openai_client: Optional[instructor.Instructor] = None

    def __init__(self, model: Optional[str] = None):
        super().__init__()
        self.model = model if model is not None else self.model
        self._openai_client = instructor.from_openai(
            OpenAI(api_key=OPENAI_API_KEY),
            mode=instructor.Mode.TOOLS,
        )

    @weave.op()
    def compose_judgement(
        self,
        question: str,
        context: str,
        ground_truth_answer: str,
        assistant_answer: str,
        total_marks: int,
    ) -> JudgeResponse:
        system_prompt = f"""
You are an expert in teacher of English langugage and literature.
Given a question, a context, a ground truth answer and an answer from an AI assistant,
you have to judge the assistant's answer based on the following criteria and assign
a score between 0 and total marks:

1. how well the assistant answers the question with respect to the context.
2. how well the assistant's answer holds up in correctness and relevance to
    the ground truth answer (assuming the ground truth answer is perfect).

You have to extract the marks to be awarded to the assistant's answer and a detailed
explanation as to how the assistant's answer was judged."""
        user_prompt = f"""
We have asked the following question to an AI assistant for total marks of {total_marks}:

---
{question}
---

We have provided context information below. 

---
{context}
---

Th AI assistant has responded with the following answer:

---
{assistant_answer}
---

An ideal answer to the question would be the following:

---
{ground_truth_answer}
---"""
        return self._openai_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            max_retries=self.max_retries,
            model=self.model,
            response_model=JudgeResponse,
        )

    @weave.op()
    def score(
        self,
        question: str,
        answer: str,
        marks: str,
        model_output: Dict[str, str],
    ) -> Dict[str, float]:
        if marks == "3-4":
            total_marks = 4
        elif marks == "5-6":
            total_marks = 6
        else:
            total_marks = 4
        judge_response = self.compose_judgement(
            question=question,
            context=model_output["context"],
            ground_truth_answer=answer,
            assistant_answer=model_output["response"],
            total_marks=total_marks,
        )
        if not hasattr(judge_response, "marks"):
            return {"marks": 0.0, "fractional_marks": 0.0, "percentage": 0.0}
        return {
            "marks": judge_response.marks,
            "fractional_marks": judge_response.marks / total_marks,
            "percentage": (judge_response.marks / total_marks) * 100,
        }
```

## Evaluating our LLM Application

Finally, let us put everything and evaluate our LLM assistant using [`weave.Evaluation`](https://wandb.github.io/weave/guides/core-types/evaluations).

```python
assistant = EnglishStudentResponseAssistant()

# We write an infer function for the evaluation process to match the
# function signature with the schema of the dataset.
@weave.op()
async def get_assistant_prediction(question: str, marks: str):
    if marks == "3-4":
        total_marks = 4
    elif marks == "5-6":
        total_marks = 6
    else:
        total_marks = 4
    return assistant.predict(question, total_marks)


# Get weave dataset
dataset = weave.ref("flamingos-prose-question-bank:v1").get()

# Define evaluation
evaluation = weave.Evaluation(dataset=dataset, scorers=[OpenaAIJudgeModel()])

# Evaluate the inference function
await evaluation.evaluate(get_assistant_prediction)
```

**NOTE:** If you're running the code from a python script, run the evaluation in the following manner:

```python
asyncio.run(evaluation.evaluate(get_assistant_prediction))
```

At the end of the evaluation we get an evaluation summary like the following:

```python
{
    'OpenaAIJudgeModel': {
        'marks': {'mean': 2.5579608938547485},
        'fractional_marks': {'mean': 0.5561568901303537},
        'percentage': {'mean': 55.615689013035386}
    },
    'model_latency': {'mean': 0.38766170946579404}
}
```

| ![](./images/weave_evaluation_dashboard.gif) |
|---|
| Using the [`weave.Evaluation`](https://wandb.github.io/weave/guides/core-types/evaluations) class, you can be sure you're comparing apples-to-apples by keeping track of all of the details that you're experimenting and evaluating with. Weave will take each example, pass it through your application and score the output on multiple custom scoring functions. By doing this, you'll have a view of the performance of your application, and a rich UI to drill into individual ouputs and scores. |


## Conclusion

- We've learnt how to build an LLM appliction using frameworks like [LlamaIndex](https://www.llamaindex.ai/) and [Instructor](https://python.useinstructor.com/).
- We've learnt how to use [GroqCloud](https://groq.com/) as an LLM vendor for our LLM application.
- We've also learned how to build observability into different steps of our applications using [`weave.op()`](../../../quickstart.md).
- We've also learned how to build more complex scoring functions, like an LLM judge, for doing automatic evaluation of application responses.
