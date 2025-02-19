# Google Gemini

:::tip
For the latest tutorials, visit [Weights & Biases on Google Cloud](https://wandb.ai/site/partners/googlecloud/).
:::

:::note
Do you want to experiment with Google Gemini models on Weave without any set up? Try the [LLM Playground](../tools/playground.md).
:::

Google offers two ways of calling Gemini via API:

1. Via the [Vertex APIs](https://cloud.google.com/vertex-ai/docs).
2. Via the [Gemini API SDK](https://ai.google.dev/gemini-api/docs/quickstart?lang=python).

## Tracing

It’s important to store traces of language model applications in a central location, both during development and in production. These traces can be useful for debugging, and as a dataset that will help you improve your application.

Weave will automatically capture traces for [Gemini API SDK](https://ai.google.dev/gemini-api/docs/quickstart?lang=python). To start tracking, calling `weave.init(project_name="<YOUR-WANDB-PROJECT-NAME>")` and use the library as normal.

```python
import os
import google.generativeai as genai
import weave

weave.init(project_name="google-ai-studio-test")

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")
response = model.generate_content("Write a story about an AI and magic")
```

Weave will also automatically capture traces for [Vertex APIs](https://cloud.google.com/vertexai/docs). To start tracking, calling `weave.init(project_name="<YOUR-WANDB-PROJECT-NAME>")` and use the library as normal.

```python
import vertexai
import weave
from vertexai.generative_models import GenerativeModel

weave.init(project_name="vertex-ai-test")
vertexai.init(project="<YOUR-VERTEXAIPROJECT-NAME>", location="<YOUR-VERTEXAI-PROJECT-LOCATION>")
model = GenerativeModel("gemini-1.5-flash-002")
response = model.generate_content(
    "What's a good name for a flower shop specialising in selling dried flower bouquets?"
)
```

## Track your own ops

Wrapping a function with `@weave.op` starts capturing inputs, outputs and app logic so you can debug how data flows through your app. You can deeply nest ops and build a tree of functions that you want to track. This also starts automatically versioning code as you experiment to capture ad-hoc details that haven't been committed to git.

Simply create a function decorated with [`@weave.op`](/guides/tracking/ops).

In the example below, we have the function `recommend_places_to_visit` which is a function wrapped with `@weave.op` that recommends places to visit in a city.

```python
import os
import google.generativeai as genai
import weave

weave.init(project_name="google_ai_studio-test")
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])


@weave.op()
def recommend_places_to_visit(city: str, model: str = "gemini-1.5-flash"):
    model = genai.GenerativeModel(
        model_name=model,
        system_instruction="You are a helpful assistant meant to suggest all budget-friendly places to visit in a city",
    )
    response = model.generate_content(city)
    return response.text


recommend_places_to_visit("New York")
recommend_places_to_visit("Paris")
recommend_places_to_visit("Kolkata")
```

## Create a `Model` for easier experimentation

Organizing experimentation is difficult when there are many moving pieces. By using the [`Model`](../core-types/models) class, you can capture and organize the experimental details of your app like your system prompt or the model you're using. This helps organize and compare different iterations of your app. 

In addition to versioning code and capturing inputs/outputs, [`Model`](../core-types/models)s capture structured parameters that control your application’s behavior, making it easy to find what parameters worked best. You can also use Weave Models with `serve`, and [`Evaluation`](../core-types/evaluations.md)s.

In the example below, you can experiment with `CityVisitRecommender`. Every time you change one of these, you'll get a new _version_ of `CityVisitRecommender`.

```python
import os
import google.generativeai as genai
import weave


class CityVisitRecommender(weave.Model):
    model: str

    @weave.op()
    def predict(self, city: str) -> str:
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction="You are a helpful assistant meant to suggest all budget-friendly places to visit in a city",
        )
        response = model.generate_content(city)
        return response.text


weave.init(project_name="google_ai_studio-test")
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
city_recommender = CityVisitRecommender(model="gemini-1.5-flash")
print(city_recommender.predict("New York"))
print(city_recommender.predict("San Francisco"))
print(city_recommender.predict("Los Angeles"))
```

### Serving a Weave Model

Given a weave reference to any `weave.Model` object, you can spin up a fastapi server and [serve](https://wandb.github.io/weave/guides/tools/serve) it. You can serve your model by using the following command in the terminal:

```shell
weave serve weave:///your_entity/project-name/YourModel:<hash>
```
