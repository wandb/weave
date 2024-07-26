# Tutorial: Model-Based Evaluation of RAG applications

Retrieval Augmented Generation (RAG) is a common way of building Generative AI applications that have access to custom knowledge bases. 

In this example, we'll show an example that has a retrieval step to get documents. By tracking this, you can debug your app and see what documents were pulled into the LLM context.
We'll also show how to evaluate it using an LLM judge.

![Evals hero](../static/img/evals-hero.png)

## 1. Build a knowledge base

First, we compute the embeddings for our articles. You would typically do this once with your articles and put the embeddings & metadata in a database, but here we're doing it every time we run our script for simplicity.

```python
from openai import OpenAI
import weave
from weave import Model
import numpy as np
import json
import asyncio 

articles = [
    "Novo Nordisk and Eli Lilly rival soars 32 percent after promising weight loss drug results Shares of Denmarks Zealand Pharma shot 32 percent higher in morning trade, after results showed success in its liver disease treatment survodutide, which is also on trial as a drug to treat obesity. The trial “tells us that the 6mg dose is safe, which is the top dose used in the ongoing [Phase 3] obesity trial too,” one analyst said in a note. The results come amid feverish investor interest in drugs that can be used for weight loss.",
    "Berkshire shares jump after big profit gain as Buffetts conglomerate nears $1 trillion valuation Berkshire Hathaway shares rose on Monday after Warren Buffetts conglomerate posted strong earnings for the fourth quarter over the weekend. Berkshires Class A and B shares jumped more than 1.5%, each. Class A shares are higher by more than 17% this year, while Class B have gained more than 18%. Berkshire was last valued at $930.1 billion, up from $905.5 billion where it closed on Friday, according to FactSet. Berkshire on Saturday posted fourth-quarter operating earnings of $8.481 billion, about 28 percent higher than the $6.625 billion from the year-ago period, driven by big gains in its insurance business. Operating earnings refers to profits from businesses across insurance, railroads and utilities. Meanwhile, Berkshires cash levels also swelled to record levels. The conglomerate held $167.6 billion in cash in the fourth quarter, surpassing the $157.2 billion record the conglomerate held in the prior quarter.",
    "Highmark Health says its combining tech from Google and Epic to give doctors easier access to information Highmark Health announced it is integrating technology from Google Cloud and the health-care software company Epic Systems. The integration aims to make it easier for both payers and providers to access key information they need, even if its stored across multiple points and formats, the company said. Highmark is the parent company of a health plan with 7 million members, a provider network of 14 hospitals and other entities",
    "Rivian and Lucid shares plunge after weak EV earnings reports Shares of electric vehicle makers Rivian and Lucid fell Thursday after the companies reported stagnant production in their fourth-quarter earnings after the bell Wednesday. Rivian shares sank about 25 percent, and Lucids stock dropped around 17 percent. Rivian forecast it will make 57,000 vehicles in 2024, slightly less than the 57,232 vehicles it produced in 2023. Lucid said it expects to make 9,000 vehicles in 2024, more than the 8,428 vehicles it made in 2023.",
    "Mauritius blocks Norwegian cruise ship over fears of a potential cholera outbreak Local authorities on Sunday denied permission for the Norwegian Dawn ship, which has 2,184 passengers and 1,026 crew on board, to access the Mauritius capital of Port Louis, citing “potential health risks.” The Mauritius Ports Authority said Sunday that samples were taken from at least 15 passengers on board the cruise ship. A spokesperson for the U.S.-headquartered Norwegian Cruise Line Holdings said Sunday that 'a small number of guests experienced mild symptoms of a stomach-related illness' during Norwegian Dawns South Africa voyage.",
    "Intuitive Machines lands on the moon in historic first for a U.S. company Intuitive Machines Nova-C cargo lander, named Odysseus after the mythological Greek hero, is the first U.S. spacecraft to soft land on the lunar surface since 1972. Intuitive Machines is the first company to pull off a moon landing — government agencies have carried out all previously successful missions. The companys stock surged in extended trading Thursday, after falling 11 percent in regular trading.",
    "Lunar landing photos: Intuitive Machines Odysseus sends back first images from the moon Intuitive Machines cargo moon lander Odysseus returned its first images from the surface. Company executives believe the lander caught its landing gear sideways in the moons surface while touching down and tipped over. Despite resting on its side, the companys historic IM-1 mission is still operating on the moon.",
]

def docs_to_embeddings(docs: list) -> list:
    openai = OpenAI()
    document_embeddings = []
    for doc in docs:
        response = (
            openai.embeddings.create(input=doc, model="text-embedding-3-small")
            .data[0]
            .embedding
        )
        document_embeddings.append(response)
    return document_embeddings

article_embeddings = docs_to_embeddings(articles) # Note: you would typically do this once with your articles and put the embeddings & metadata in a database
```

## 2. Create a RAG app

Next, we wrap our retrieval function `get_most_relevant_document` with a `weave.op()` decorator and we create our `Model` class. We call `weave.init('rag-qa')` to begin tracking all the inputs and outputs of our functions for later inspection.

```python
from openai import OpenAI
import weave
from weave import Model
import numpy as np
import asyncio

# highlight-next-line
@weave.op()
def get_most_relevant_document(query):
    openai = OpenAI()
    query_embedding = (
        openai.embeddings.create(input=query, model="text-embedding-3-small")
        .data[0]
        .embedding
    )
    similarities = [
        np.dot(query_embedding, doc_emb)
        / (np.linalg.norm(query_embedding) * np.linalg.norm(doc_emb))
        for doc_emb in article_embeddings
    ]
    # Get the index of the most similar document
    most_relevant_doc_index = np.argmax(similarities)
    return articles[most_relevant_doc_index]

# highlight-next-line
class RAGModel(Model):
    system_message: str
    model_name: str = "gpt-3.5-turbo-1106"

# highlight-next-line
    @weave.op()
    def predict(self, question: str) -> dict: # note: `question` will be used later to select data from our evaluation rows
        from openai import OpenAI
        context = get_most_relevant_document(question)
        client = OpenAI()
        query = f"""Use the following information to answer the subsequent question. If the answer cannot be found, write "I don't know."
        Context:
        \"\"\"
        {context}
        \"\"\"
        Question: {question}"""
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            response_format={"type": "text"},
        )
        answer = response.choices[0].message.content
        return {'answer': answer, 'context': context}

# highlight-next-line
weave.init('rag-qa')
model = RAGModel(
    system_message="You are an expert in finance and answer questions related to finance, financial services, and financial markets. When responding based on provided information, be sure to cite the source."
)
model.predict("What significant result was reported about Zealand Pharma's obesity trial?")
```

## 3. Evaluating with an LLM Judge

When there aren't simple ways to evaluate your application, one approach is to use an LLM to evaluate aspects of it. Here is an example of using an LLM judge to try to measure the context precision by prompting it to verify if the context was useful in arriving at the given answer. This prompt was augmented from the popular [RAGAS framework](https://docs.ragas.io/). 

### Defining a scoring function

As we did in the [Build an Evaluation pipeline tutorial](/tutorial-eval), we'll define a set of example rows to test our app against and a scoring function. Our scoring function will take one row and evaluate it. The input arguments should match with the corresponding keys in our row, so `question` here will be taken from the row dictionary. `model_output` is the output of the model. The input to the model will be taken from the example based on its input argument, so `question` here too. We're using `async` functions so they run fast in parallel. If you need a quick introduction to async, you can find one [here](https://docs.python.org/3/library/asyncio.html).

```python
from openai import OpenAI
import weave
import asyncio

# highlight-next-line
@weave.op()
async def context_precision_score(question, model_output):
    context_precision_prompt = """Given question, answer and context verify if the context was useful in arriving at the given answer. Give verdict as "1" if useful and "0" if not with json output. 
    Output in only valid JSON format.

    question: {question}
    context: {context}
    answer: {answer}
    verdict: """
    client = OpenAI()

    prompt = context_precision_prompt.format(
        question=question,
        context=model_output['context'],
        answer=model_output['answer'],
    )

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    response_message = response.choices[0].message
    response = json.loads(response_message.content)
    return {
        "verdict": int(response["verdict"]) == 1,
    }

questions = [
    {"question": "What significant result was reported about Zealand Pharma's obesity trial?"},
    {"question": "How much did Berkshire Hathaway's cash levels increase in the fourth quarter?"},
    {"question": "What is the goal of Highmark Health's integration of Google Cloud and Epic Systems technology?"},
    {"question": "What were Rivian and Lucid's vehicle production forecasts for 2024?"},
    {"question": "Why was the Norwegian Dawn cruise ship denied access to Mauritius?"},
    {"question": "Which company achieved the first U.S. moon landing since 1972?"},
    {"question": "What issue did Intuitive Machines' lunar lander encounter upon landing on the moon?"}
]
# highlight-next-line
evaluation = weave.Evaluation(dataset=questions, scorers=[context_precision_score])
# highlight-next-line
asyncio.run(evaluation.evaluate(model)) # note: you'll need to define a model to evaluate
```

### Optional: Defining a `Scorer` class
In some applications we want to create custom evaluation classes - where for example a standardized `LLMJudge` class should be created with specific parameters (e.g. chat model, prompt), specific scoring of each row, and specific calculation of an aggregate score. In order to do that Weave defines a list of ready-to-use `Scorer` classes and also makes it easy to create a custom `Scorer` - in the following we'll see how to create a custom `class CorrectnessLLMJudge(Scorer)`. 

On a high-level the steps to create custom Scorer are quite simple: 
1. Define a custom class that inherits from `weave.flow.scorer.Scorer`
2. Overwrite the `score` function and add a `@weave.op()` if you want to track each call of the function
    - this function has to define a `model_output` argument where the prediction of the model will be passed to. We define it as type `Optional[dict]` in case the mode might return "None".
    - the rest of the arguments can either be a general `Any` or `dict` or can select specific columns from the dataset that is used to evaluate the model using the `weave.Evaluate` class - they have to have the exact same names as the column names or keys of a single row after being passed to `preprocess_model_input` if that is used.
3. *Optional:* Overwrite the `summarize` function to customize the calculation of the aggregate score. By default Weave uses the `weave.flow.scorer.auto_summarize` function if you don't define a custom function.
    - this function has to have a `@weave.op()` decorator.


```python
from weave.flow.scorer import Scorer
from weave import WeaveList

class CorrectnessLLMJudge(Scorer):
    prompt: str
    model_name: str
    device: str

    @weave.op()
    async def score(self, model_output: Optional[dict], query: str, answer: str) -> Any:
        """Score the correctness of the predictions by comparing the pred, query, target.
           Args:
            - model_output: the dict that will be provided by the model that is evaluated
            - query: the question asked - as defined in the dataset
            - answer: the target answer - as defined in the dataset
           Returns:
            - single dict {metric name: single evaluation value}"""

        # get_model is defined as general model getter based on provided params (OpenAI,HF...)
        eval_model = get_model(
            model_name = self.model_name,
            prompt = self.prompt
            device = self.device,
        )
        # async evaluation to speed up evaluation - this doesn't have to be async
        grade = await eval_model.async_predict(
            {
                "query": query,
                "answer": answer,
                "result": model_output.get("result"),
            }
        )
        # output parsing - could be done more reobustly with pydantic
        evaluation = "incorrect" not in grade["text"].strip().lower()

        # the column name displayed in Weave
        return {"correct": evaluation}

    @weave.op()
    def summarize(self, score_rows: WeaveList) -> Optional[dict]:
        """Aggregate all the scores that are calculated for each row by the scoring function.
           Args:
            - score_rows: a WeaveList object, nested dict of metrics and scores
           Returns:
            - nested dict with the same structure as the input"""
        
        # if nothing is provided the weave.flow.scorer.auto_summarize function is used
        # return auto_summarize(score_rows)

        valid_data = [x.get("correct") for x in score_rows if x.get("correct") is not None]
        count_true = list(valid_data).count(True)
        int_data = [int(x) for x in valid_data]

        sample_mean = np.mean(int_data) if int_data else 0
        sample_variance = np.var(int_data) if int_data else 0
        sample_error = np.sqrt(sample_variance / len(int_data)) if int_data else 0

        # the extra "correct" layer is not necessary but adds structure in the UI
        return {
            "correct": {
                "true_count": count_true,
                "true_fraction": sample_mean,
                "stderr": sample_error,
            }
        }
```

To use this as a scorer, you would initialize it and pass it to `scorers` argument in your `Evaluation like this:

```python
evaluation = weave.Evaluation(dataset=questions, scorers=[CorrectnessLLMJudge()])
```

## 4. Pulling it all together

To get the same result for your RAG apps:
- Wrap LLM calls & retrieval step functions with `weave.op()`
- (optional) Create a `Model` subclass with `predict` function and app details
- Collect examples to evaluate
- Create scoring functions that score one example
- Use `Evaluation` class to run evaluations on your examples

**NOTE:** Sometimes the async execution of Evaluations will trigger a rate limit on the models of OpenAI, Anthropic, etc. To prevent that you can set an environment variable to limit the amount of parallel workers e.g. `WEAVE_PARALLELISM=3`.

Here, we show the code in it's entirety.

```python
from openai import OpenAI
import weave
from weave import Model
import numpy as np
import json
import asyncio 

# Examples we've gathered that we want to use for evaluations
articles = [
    "Novo Nordisk and Eli Lilly rival soars 32 percent after promising weight loss drug results Shares of Denmarks Zealand Pharma shot 32 percent higher in morning trade, after results showed success in its liver disease treatment survodutide, which is also on trial as a drug to treat obesity. The trial “tells us that the 6mg dose is safe, which is the top dose used in the ongoing [Phase 3] obesity trial too,” one analyst said in a note. The results come amid feverish investor interest in drugs that can be used for weight loss.",
    "Berkshire shares jump after big profit gain as Buffetts conglomerate nears $1 trillion valuation Berkshire Hathaway shares rose on Monday after Warren Buffetts conglomerate posted strong earnings for the fourth quarter over the weekend. Berkshires Class A and B shares jumped more than 1.5%, each. Class A shares are higher by more than 17% this year, while Class B have gained more than 18%. Berkshire was last valued at $930.1 billion, up from $905.5 billion where it closed on Friday, according to FactSet. Berkshire on Saturday posted fourth-quarter operating earnings of $8.481 billion, about 28 percent higher than the $6.625 billion from the year-ago period, driven by big gains in its insurance business. Operating earnings refers to profits from businesses across insurance, railroads and utilities. Meanwhile, Berkshires cash levels also swelled to record levels. The conglomerate held $167.6 billion in cash in the fourth quarter, surpassing the $157.2 billion record the conglomerate held in the prior quarter.",
    "Highmark Health says its combining tech from Google and Epic to give doctors easier access to information Highmark Health announced it is integrating technology from Google Cloud and the health-care software company Epic Systems. The integration aims to make it easier for both payers and providers to access key information they need, even if its stored across multiple points and formats, the company said. Highmark is the parent company of a health plan with 7 million members, a provider network of 14 hospitals and other entities",
    "Rivian and Lucid shares plunge after weak EV earnings reports Shares of electric vehicle makers Rivian and Lucid fell Thursday after the companies reported stagnant production in their fourth-quarter earnings after the bell Wednesday. Rivian shares sank about 25 percent, and Lucids stock dropped around 17 percent. Rivian forecast it will make 57,000 vehicles in 2024, slightly less than the 57,232 vehicles it produced in 2023. Lucid said it expects to make 9,000 vehicles in 2024, more than the 8,428 vehicles it made in 2023.",
    "Mauritius blocks Norwegian cruise ship over fears of a potential cholera outbreak Local authorities on Sunday denied permission for the Norwegian Dawn ship, which has 2,184 passengers and 1,026 crew on board, to access the Mauritius capital of Port Louis, citing “potential health risks.” The Mauritius Ports Authority said Sunday that samples were taken from at least 15 passengers on board the cruise ship. A spokesperson for the U.S.-headquartered Norwegian Cruise Line Holdings said Sunday that 'a small number of guests experienced mild symptoms of a stomach-related illness' during Norwegian Dawns South Africa voyage.",
    "Intuitive Machines lands on the moon in historic first for a U.S. company Intuitive Machines Nova-C cargo lander, named Odysseus after the mythological Greek hero, is the first U.S. spacecraft to soft land on the lunar surface since 1972. Intuitive Machines is the first company to pull off a moon landing — government agencies have carried out all previously successful missions. The companys stock surged in extended trading Thursday, after falling 11 percent in regular trading.",
    "Lunar landing photos: Intuitive Machines Odysseus sends back first images from the moon Intuitive Machines cargo moon lander Odysseus returned its first images from the surface. Company executives believe the lander caught its landing gear sideways in the moons surface while touching down and tipped over. Despite resting on its side, the companys historic IM-1 mission is still operating on the moon.",
]

def docs_to_embeddings(docs: list) -> list:
    openai = OpenAI()
    document_embeddings = []
    for doc in docs:
        response = (
            openai.embeddings.create(input=doc, model="text-embedding-3-small")
            .data[0]
            .embedding
        )
        document_embeddings.append(response)
    return document_embeddings

article_embeddings = docs_to_embeddings(articles) # Note: you would typically do this once with your articles and put the embeddings & metadata in a database

# We've added a decorator to our retrieval step
# highlight-next-line
@weave.op()
def get_most_relevant_document(query):
    openai = OpenAI()
    query_embedding = (
        openai.embeddings.create(input=query, model="text-embedding-3-small")
        .data[0]
        .embedding
    )
    similarities = [
        np.dot(query_embedding, doc_emb)
        / (np.linalg.norm(query_embedding) * np.linalg.norm(doc_emb))
        for doc_emb in article_embeddings
    ]
    # Get the index of the most similar document
    most_relevant_doc_index = np.argmax(similarities)
    return articles[most_relevant_doc_index]

# We create a Model subclass with some details about our app, along with a predict function that produces a response
# highlight-next-line
class RAGModel(Model):
    system_message: str
    model_name: str = "gpt-3.5-turbo-1106"

# highlight-next-line
    @weave.op()
# highlight-next-line
    def predict(self, question: str) -> dict: # note: `question` will be used later to select data from our evaluation rows
        from openai import OpenAI
        context = get_most_relevant_document(question)
        client = OpenAI()
        query = f"""Use the following information to answer the subsequent question. If the answer cannot be found, write "I don't know."
        Context:
        \"\"\"
        {context}
        \"\"\"
        Question: {question}"""
        response = client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": self.system_message},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            response_format={"type": "text"},
        )
        answer = response.choices[0].message.content
        return {'answer': answer, 'context': context}

# highlight-next-line
weave.init('rag-qa')
# highlight-next-line
model = RAGModel(
    system_message="You are an expert in finance and answer questions related to finance, financial services, and financial markets. When responding based on provided information, be sure to cite the source."
)

# Here is our scoring function uses our question and model_output to product a score
# highlight-next-line
@weave.op()
# highlight-next-line
async def context_precision_score(question, model_output):
    context_precision_prompt = """Given question, answer and context verify if the context was useful in arriving at the given answer. Give verdict as "1" if useful and "0" if not with json output. 
    Output in only valid JSON format.

    question: {question}
    context: {context}
    answer: {answer}
    verdict: """
    client = OpenAI()

    prompt = context_precision_prompt.format(
        question=question,
        context=model_output['context'],
        answer=model_output['answer'],
    )

    response = client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    response_message = response.choices[0].message
    response = json.loads(response_message.content)
    return {
        "verdict": int(response["verdict"]) == 1,
    }

questions = [
    {"question": "What significant result was reported about Zealand Pharma's obesity trial?"},
    {"question": "How much did Berkshire Hathaway's cash levels increase in the fourth quarter?"},
    {"question": "What is the goal of Highmark Health's integration of Google Cloud and Epic Systems technology?"},
    {"question": "What were Rivian and Lucid's vehicle production forecasts for 2024?"},
    {"question": "Why was the Norwegian Dawn cruise ship denied access to Mauritius?"},
    {"question": "Which company achieved the first U.S. moon landing since 1972?"},
    {"question": "What issue did Intuitive Machines' lunar lander encounter upon landing on the moon?"}
]

# We define an Evaluation object and pass our example questions along with scoring functions
# highlight-next-line
evaluation = weave.Evaluation(dataset=questions, scorers=[context_precision_score])
# highlight-next-line
asyncio.run(evaluation.evaluate(model))
```

## Conclusion

We've learned how to build observability into different steps of our applications, like the retrieval step in this example.
We've also learned how to build more complex scoring functions, like an LLM judge, for doing automatic evaluation of application responses.

## What's next?

Learn more about Weave's core types [Quickstart](/guides/core-types).
