<project title="Weave" summary="Weave is a lightweight toolkit for tracking and evaluating LLM applications, built by Weights &amp; Biases.">This document contains links to all the documentation for Weave.<docs><doc title="introduction">---
slug: /
---

# Introduction

**Weave** is a lightweight toolkit for tracking and evaluating LLM applications, built by Weights & Biases.

Our goal is to bring rigor, best-practices, and composability to the inherently experimental process of developing AI applications, without introducing cognitive overhead.

**[Get started](/quickstart)** by decorating Python functions with `@weave.op()`.

![Weave Hero](../static/img/weave-hero.png)

Seriously, try the 🍪 **[quickstart](/quickstart)** 🍪 or <a class="vertical-align-colab-button" target="\_blank" href="http://wandb.me/weave_colab" onClick={()=>{window.analytics?.track("Weave Docs: Quickstart colab clicked")}}><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

You can use Weave to:

- Log and debug language model inputs, outputs, and traces
- Build rigorous, apples-to-apples evaluations for language model use cases
- Organize all the information generated across the LLM workflow, from experimentation to evaluations to production

## What's next?

Try the [Quickstart](/quickstart) to see Weave in action.</doc><doc title="quickstart">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Track LLM inputs & outputs


Follow these steps to track your first call or <a class="vertical-align-colab-button" target="_blank" href="http://wandb.me/weave_colab"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>

## 1. Install Weave and create an API Key

**Install weave**

First install the weave library:

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```bash
    pip install weave
    ```
  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```bash
    pnpm install weave
    ```
  </TabItem>
</Tabs>

**Get your API key**

Then, create a Weights & Biases (W&B) account at https://wandb.ai and copy your API key from https://wandb.ai/authorize

## 2. Log a trace to a new project

To get started with tracking your first project with Weave:

- Import the `weave` library
- Call `weave.init('project-name')` to start tracking
  - You will be prompted to log in with your API key if you are not yet logged in on your machine.
  - To log to a specific W&B Team name, replace `project-name` with `team-name/project-name`
  - **NOTE:** In automated environments, you can define the environment variable `WANDB_API_KEY` with your API key to login without prompting.
- Add the `@weave.op()` decorator to the python functions you want to track

_In this example, we're using openai so you will need to add an OpenAI [API key](https://platform.openai.com/docs/quickstart/step-2-setup-your-api-key)._

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    # highlight-next-line
    import weave
    from openai import OpenAI

    client = OpenAI(api_key="...")

    # Weave will track the inputs, outputs and code of this function
    # highlight-next-line
    @weave.op()
    def extract_dinos(sentence: str) -> dict:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """In JSON format extract a list of `dinosaurs`, with their `name`,
    their `common_name`, and whether its `diet` is a herbivore or carnivore"""
                },
                {
                    "role": "user",
                    "content": sentence
                }
                ],
                response_format={ "type": "json_object" }
            )
        return response.choices[0].message.content


    # Initialise the weave project
    # highlight-next-line
    weave.init('jurassic-park')

    sentence = """I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike), \
    both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant \
    Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below."""

    result = extract_dinos(sentence)
    print(result)
    ```
    When you call the `extract_dinos` function Weave will output a link to view your trace.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```typescript
    import OpenAI from 'openai';
    // highlight-next-line
    import * as weave from 'weave';

    // highlight-next-line
    const openai = weave.wrapOpenAI(new OpenAI());

    async function extractDinos(input: string) {
      const response = await openai.chat.completions.create({
        model: 'gpt-4o',
        messages: [
          {
            role: 'user',
            content: `In JSON format extract a list of 'dinosaurs', with their 'name', their 'common_name', and whether its 'diet' is a herbivore or carnivore: ${input}`,
          },
        ],
      });
      return response.choices[0].message.content;
    }
    // highlight-next-line
    const extractDinosOp = weave.op(extractDinos);

    async function main() {
      // highlight-next-line
      await weave.init('examples');
      const result = await extractDinosOp(
        'I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike), both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below.'
      );
      console.log(result);
    }

    main();

    ```
    When you call the `extractDinos` function Weave will output a link to view your trace.

  </TabItem>
</Tabs>

## 3. Automated LLM library logging

Calls made to OpenAI, Anthropic and [many more LLM libraries](guides/integrations/) are automatically tracked with Weave, with **LLM metadata**, **token usage** and **cost** being logged automatically. If your LLM library isn't currently one of our integrations you can track calls to other LLMs libraries or frameworks easily by wrapping them with `@weave.op()`.

## 4. See traces of your application in your project

🎉 Congrats! Now, every time you call this function, weave will automatically capture the input & output data and log any changes made to the code.

![Weave Trace Outputs 1](../static/img/tutorial_trace_1.png)

## What's next?

- Follow the [Tracking flows and app metadata](/tutorial-tracing_2) to start tracking and the data flowing through your app.</doc><doc title="tutorial-eval">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Tutorial: Build an Evaluation pipeline

To iterate on an application, we need a way to evaluate if it's improving. To do so, a common practice is to test it against the same set of examples when there is a change. Weave has a first-class way to track evaluations with `Model` & `Evaluation` classes. We have built the APIs to make minimal assumptions to allow for the flexibility to support a wide array of use-cases.

![Evals hero](../static/img/evals-hero.png)

## 1. Build a `Model`

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>

`Model`s store and version information about your system, such as prompts, temperatures, and more.
Weave automatically captures when they are used and updates the version when there are changes.

`Model`s are declared by subclassing `Model` and implementing a `predict` function definition, which takes one example and returns the response.

:::warning

**Known Issue**: If you are using Google Colab, remove `async` from the following examples.

:::

    ```python
    import json
    import openai
    import weave

    # highlight-next-line
    class ExtractFruitsModel(weave.Model):
        model_name: str
        prompt_template: str

        # highlight-next-line
        @weave.op()
        # highlight-next-line
        async def predict(self, sentence: str) -> dict:
            client = openai.AsyncClient()

            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": self.prompt_template.format(sentence=sentence)}
                ],
            )
            result = response.choices[0].message.content
            if result is None:
                raise ValueError("No response from model")
            parsed = json.loads(result)
            return parsed
    ```

    You can instantiate `Model` objects as normal like this:

    ```python
    import asyncio
    import weave

    weave.init('intro-example')

    model = ExtractFruitsModel(model_name='gpt-3.5-turbo-1106',
                            prompt_template='Extract fields ("fruit": <str>, "color": <str>, "flavor": <str>) from the following text, as json: {sentence}')
    sentence = "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy."
    print(asyncio.run(model.predict(sentence)))
    # if you're in a Jupyter Notebook, run:
    # await model.predict(sentence)
    ```

:::note
Checkout the [Models](/guides/core-types/models) guide to learn more.
:::

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    `weave.Model` is not supported in TypeScript yet.  Instead, you can just wrap your model-like function with `weave.op`

    ```typescript
    // highlight-next-line
    const model = weave.op(async function myModel({datasetRow}) {
      const prompt = `Extract fields ("fruit": <str>, "color": <str>, "flavor") from the following text, as json: ${datasetRow.sentence}`;
      const response = await openaiClient.chat.completions.create({
        model: 'gpt-3.5-turbo',
        messages: [{role: 'user', content: prompt}],
        response_format: {type: 'json_object'},
      });
      const result = response?.choices?.[0]?.message?.content;
      if (result == null) {
        throw new Error('No response from model');
      }
      return JSON.parse(result);
    });
    ```

  </TabItem>
</Tabs>

## 2. Collect some examples

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>

    ```python
    sentences = [
        "There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.",
        "Pounits are a bright green color and are more savory than sweet.",
        "Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them."
    ]
    labels = [
        {'fruit': 'neoskizzles', 'color': 'purple', 'flavor': 'candy'},
        {'fruit': 'pounits', 'color': 'bright green', 'flavor': 'savory'},
        {'fruit': 'glowls', 'color': 'pale orange', 'flavor': 'sour and bitter'}
    ]
    examples = [
        {'id': '0', 'sentence': sentences[0], 'target': labels[0]},
        {'id': '1', 'sentence': sentences[1], 'target': labels[1]},
        {'id': '2', 'sentence': sentences[2], 'target': labels[2]}
    ]
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
  
    ```typescript
    const sentences = [
      'There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.',
      'Pounits are a bright green color and are more savory than sweet.',
      'Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them.',
    ];
    const labels = [
      {fruit: 'neoskizzles', color: 'purple', flavor: 'candy'},
      {fruit: 'pounits', color: 'bright green', flavor: 'savory'},
      {fruit: 'glowls', color: 'pale orange', flavor: 'sour and bitter'},
    ];
    const examples = [
      {id: '0', sentence: sentences[0], target: labels[0]},
      {id: '1', sentence: sentences[1], target: labels[1]},
      {id: '2', sentence: sentences[2], target: labels[2]},
    ];
    const dataset = new weave.Dataset({
      id: 'Fruit Dataset',
      rows: examples,
    });
    ```
  </TabItem>
</Tabs>

## 3. Evaluate a `Model`

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>

`Evaluation`s assess a `Model`s performance on a set of examples using a list of specified scoring functions or `weave.scorer.Scorer` classes.

Here, we'll use a default scoring class `MultiTaskBinaryClassificationF1` and we'll also define our own `fruit_name_score` scoring function.

Here `sentence` is passed to the model's predict function, and `target` is used in the scoring function, these are inferred based on the argument names of the `predict` and scoring functions. The `fruit` key needs to be outputted by the model's predict function and must also be existing as a column in the dataset (or outputted by the `preprocess_model_input` function if defined).

    ```python
    import weave
    from weave.scorers import MultiTaskBinaryClassificationF1

    weave.init('intro-example')

    @weave.op()
    def fruit_name_score(target: dict, output: dict) -> dict:
        return {'correct': target['fruit'] == output['fruit']}

    # highlight-next-line
    evaluation = weave.Evaluation(
        # highlight-next-line
        dataset=examples,
        # highlight-next-line
        scorers=[
            # highlight-next-line
            MultiTaskBinaryClassificationF1(class_names=["fruit", "color", "flavor"]),
            # highlight-next-line
            fruit_name_score
        # highlight-next-line
        ],
    # highlight-next-line
    )
    # highlight-next-line
    print(asyncio.run(evaluation.evaluate(model)))
    # if you're in a Jupyter Notebook, run:
    # await evaluation.evaluate(model)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
`Evaluation`s assess a model's performance on a set of examples using a list of specified scoring functions.

For this example, we'll define a few simple scoring functions.

Here, `sentence` is passed to the model and `...` is used in the scoring function. These are defined...

    ```typescript
    import * as weave from 'weave';
    import {OpenAI} from 'openai';

    const client = await weave.init('intro-example');
    const openaiClient = weave.wrapOpenAI(new OpenAI());

    const fruitNameScorer = weave.op(
      ({modelOutput, datasetRow}) => datasetRow.target.fruit == modelOutput.fruit,
      {name: 'fruitNameScore'}
    );

    const evaluation = new weave.Evaluation({
      dataset: ds,
      scorers: [fruitNameScorer],
    });

    const results = await evaluation.evaluate(model);
    console.log(JSON.stringify(results, null, 2));
    ```

  </TabItem>
</Tabs>

In some applications we want to create custom `Scorer` classes - where for example a standardized `LLMJudge` class should be created with specific parameters (e.g. chat model, prompt), specific scoring of each row, and specific calculation of an aggregate score. See the tutorial on defining a `Scorer` class in the next chapter on [Model-Based Evaluation of RAG applications](/tutorial-rag#optional-defining-a-scorer-class) for more information.

## 4. Pulling it all together

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
  
    ```python
    import json
    import asyncio
    # highlight-next-line
    import weave
    # highlight-next-line
    from weave.scorers import MultiTaskBinaryClassificationF1
    import openai

    # We create a model class with one predict function.
    # All inputs, predictions and parameters are automatically captured for easy inspection.

    # highlight-next-line
    class ExtractFruitsModel(weave.Model):
        model_name: str
        prompt_template: str

        # highlight-next-line
        @weave.op()
        # highlight-next-line
        async def predict(self, sentence: str) -> dict:
            client = openai.AsyncClient()

            response = await client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "user", "content": self.prompt_template.format(sentence=sentence)}
                ],
                response_format={ "type": "json_object" }
            )
            result = response.choices[0].message.content
            if result is None:
                raise ValueError("No response from model")
            parsed = json.loads(result)
            return parsed

    # We call init to begin capturing data in the project, intro-example.
    weave.init('intro-example')

    # We create our model with our system prompt.
    model = ExtractFruitsModel(name='gpt4',
                            model_name='gpt-4-0125-preview',
                            prompt_template='Extract fields ("fruit": <str>, "color": <str>, "flavor") from the following text, as json: {sentence}')
    sentences = ["There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.",
    "Pounits are a bright green color and are more savory than sweet.",
    "Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them."]
    labels = [
        {'fruit': 'neoskizzles', 'color': 'purple', 'flavor': 'candy'},
        {'fruit': 'pounits', 'color': 'bright green', 'flavor': 'savory'},
        {'fruit': 'glowls', 'color': 'pale orange', 'flavor': 'sour and bitter'}
    ]
    examples = [
        {'id': '0', 'sentence': sentences[0], 'target': labels[0]},
        {'id': '1', 'sentence': sentences[1], 'target': labels[1]},
        {'id': '2', 'sentence': sentences[2], 'target': labels[2]}
    ]
    # If you have already published the Dataset, you can run:
    # dataset = weave.ref('example_labels').get()

    # We define a scoring function to compare our model predictions with a ground truth label.
    @weave.op()
    def fruit_name_score(target: dict, output: dict) -> dict:
        return {'correct': target['fruit'] == output['fruit']}

    # Finally, we run an evaluation of this model.
    # This will generate a prediction for each input example, and then score it with each scoring function.
    # highlight-next-line
    evaluation = weave.Evaluation(
        # highlight-next-line
        name='fruit_eval',
        # highlight-next-line
        dataset=examples, scorers=[MultiTaskBinaryClassificationF1(class_names=["fruit", "color", "flavor"]), fruit_name_score],
    # highlight-next-line
    )
    print(asyncio.run(evaluation.evaluate(model)))
    # if you're in a Jupyter Notebook, run:
    # await evaluation.evaluate(model)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    ```typescript
    import {OpenAI} from 'openai';
    import 'source-map-support/register';
    import * as weave from 'weave';

    const sentences = [
      'There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.',
      'Pounits are a bright green color and are more savory than sweet.',
      'Finally, there are fruits called glowls, which have a very sour and bitter taste which is acidic and caustic, and a pale orange tinge to them.',
      'There are many fruits that were found on the recently discovered planet Goocrux. There are neoskizzles that grow there, which are purple and taste like candy.',
    ];
    const labels = [
      {fruit: 'neoskizzles', color: 'purple', flavor: 'candy'},
      {fruit: 'pounits', color: 'bright green', flavor: 'savory'},
      {fruit: 'glowls', color: 'pale orange', flavor: 'sour and bitter'},
    ];
    const examples = [
      {id: '0', sentence: sentences[0], target: labels[0]},
      {id: '1', sentence: sentences[1], target: labels[1]},
      {id: '2', sentence: sentences[2], target: labels[2]},
    ];
    const dataset = new weave.Dataset({
      id: 'Fruit Dataset',
      rows: examples,
    });

    const openaiClient = weave.wrapOpenAI(new OpenAI());

    const model = weave.op(async function myModel({datasetRow}) {
      const prompt = `Extract fields ("fruit": <str>, "color": <str>, "flavor") from the following text, as json: ${datasetRow.sentence}`;
      const response = await openaiClient.chat.completions.create({
        model: 'gpt-3.5-turbo',
        messages: [{role: 'user', content: prompt}],
        response_format: {type: 'json_object'},
      });
      const result = response?.choices?.[0]?.message?.content;
      if (result == null) {
        throw new Error('No response from model');
      }
      return JSON.parse(result);
    });

    const fruitNameScorer = weave.op(
      ({modelOutput, datasetRow}) => datasetRow.target.fruit == modelOutput.fruit,
      {name: 'fruitNameScore'}
    );

    async function main() {
      await weave.init('examples');
      const evaluation = new weave.Evaluation({
        dataset,
        scorers: [fruitNameScorer],
      });

      const results = await evaluation.evaluate({model});
      console.log(JSON.stringify(results, null, 2));
    }

    main();

    ```

  </TabItem>
</Tabs>

## What's next?

- Follow the [Model-Based Evaluation of RAG applications](/tutorial-rag) to evaluate a RAG app using an LLM judge.</doc><doc title="tutorial-rag">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Tutorial: Model-Based Evaluation of RAG applications

:::warning

This tutorial is currently only available for Python!

:::

Retrieval Augmented Generation (RAG) is a common way of building Generative AI applications that have access to custom knowledge bases.

In this example, we'll show an example that has a retrieval step to get documents. By tracking this, you can debug your app and see what documents were pulled into the LLM context.
We'll also show how to evaluate it using an LLM judge.

![Evals hero](../static/img/evals-hero.png)

Check out the [RAG++ course](https://www.wandb.courses/courses/rag-in-production?utm_source=wandb_docs&utm_medium=code&utm_campaign=weave_docs) for a more advanced dive into practical RAG techniques for engineers, where you'll learn production-ready solutions from Weights & Biases, Cohere and Weaviate to optimize performance, cut costs, and enhance the accuracy and relevance of your applications.

## 1. Build a knowledge base

First, we compute the embeddings for our articles. You would typically do this once with your articles and put the embeddings & metadata in a database, but here we're doing it every time we run our script for simplicity.

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    from openai import OpenAI
    import weave
    from weave import Model
    import numpy as np
    import json
    import asyncio

    articles = [
        "Novo Nordisk and Eli Lilly rival soars 32 percent after promising weight loss drug results Shares of Denmarks Zealand Pharma shot 32 percent higher in morning trade, after results showed success in its liver disease treatment survodutide, which is also on trial as a drug to treat obesity. The trial “tells us that the 6mg dose is safe, which is the top dose used in the ongoing [Phase 3] obesity trial too,” one analyst said in a note. The results come amid feverish investor interest in drugs that can be used for weight loss.",
        "Berkshire shares jump after big profit gain as Buffetts conglomerate nears $1 trillion valuation Berkshire Hathaway shares rose on Monday after Warren Buffetts conglomerate posted strong earnings for the fourth quarter over the weekend. Berkshires Class A and B shares jumped more than 1.5%, each. Class A shares are higher by more than 17% this year, while Class B has gained more than 18%. Berkshire was last valued at $930.1 billion, up from $905.5 billion where it closed on Friday, according to FactSet. Berkshire on Saturday posted fourth-quarter operating earnings of $8.481 billion, about 28 percent higher than the $6.625 billion from the year-ago period, driven by big gains in its insurance business. Operating earnings refers to profits from businesses across insurance, railroads and utilities. Meanwhile, Berkshires cash levels also swelled to record levels. The conglomerate held $167.6 billion in cash in the fourth quarter, surpassing the $157.2 billion record the conglomerate held in the prior quarter.",
        "Highmark Health says its combining tech from Google and Epic to give doctors easier access to information Highmark Health announced it is integrating technology from Google Cloud and the health-care software company Epic Systems. The integration aims to make it easier for both payers and providers to access key information they need, even if its stored across multiple points and formats, the company said. Highmark is the parent company of a health plan with 7 million members, a provider network of 14 hospitals and other entities",
        "Rivian and Lucid shares plunge after weak EV earnings reports Shares of electric vehicle makers Rivian and Lucid fell Thursday after the companies reported stagnant production in their fourth-quarter earnings after the bell Wednesday. Rivian shares sank about 25 percent, and Lucids stock dropped around 17 percent. Rivian forecast it will make 57,000 vehicles in 2024, slightly less than the 57,232 vehicles it produced in 2023. Lucid said it expects to make 9,000 vehicles in 2024, more than the 8,428 vehicles it made in 2023.",
        "Mauritius blocks Norwegian cruise ship over fears of a potential cholera outbreak Local authorities on Sunday denied permission for the Norwegian Dawn ship, which has 2,184 passengers and 1,026 crew on board, to access the Mauritius capital of Port Louis, citing “potential health risks.” The Mauritius Ports Authority said Sunday that samples were taken from at least 15 passengers on board the cruise ship. A spokesperson for the U.S.-headquartered Norwegian Cruise Line Holdings said Sunday that 'a small number of guests experienced mild symptoms of a stomach-related illness' during Norwegian Dawns South Africa voyage.",
        "Intuitive Machines lands on the moon in historic first for a U.S. company Intuitive Machines Nova-C cargo lander, named Odysseus after the mythological Greek hero, is the first U.S. spacecraft to soft land on the lunar surface since 1972. Intuitive Machines is the first company to pull off a moon landing — government agencies have carried out all previously successful missions. The company's stock surged in extended trading Thursday, after falling 11 percent in regular trading.",
        "Lunar landing photos: Intuitive Machines Odysseus sends back first images from the moon Intuitive Machines cargo moon lander Odysseus returned its first images from the surface. Company executives believe the lander caught its landing gear sideways on the moon's surface while touching down and tipped over. Despite resting on its side, the company's historic IM-1 mission is still operating on the moon.",
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

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## 2. Create a RAG app

Next, we wrap our retrieval function `get_most_relevant_document` with a `weave.op()` decorator and we create our `Model` class. We call `weave.init('rag-qa')` to begin tracking all the inputs and outputs of our functions for later inspection.

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
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

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## 3. Evaluating with an LLM Judge

When there aren't simple ways to evaluate your application, one approach is to use an LLM to evaluate aspects of it. Here is an example of using an LLM judge to try to measure the context precision by prompting it to verify if the context was useful in arriving at the given answer. This prompt was augmented from the popular [RAGAS framework](https://docs.ragas.io/).

### Defining a scoring function

As we did in the [Build an Evaluation pipeline tutorial](/tutorial-eval), we'll define a set of example rows to test our app against and a scoring function. Our scoring function will take one row and evaluate it. The input arguments should match with the corresponding keys in our row, so `question` here will be taken from the row dictionary. `output` is the output of the model. The input to the model will be taken from the example based on its input argument, so `question` here too. We're using `async` functions so they run fast in parallel. If you need a quick introduction to async, you can find one [here](https://docs.python.org/3/library/asyncio.html).

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    from openai import OpenAI
    import weave
    import asyncio

    # highlight-next-line
    @weave.op()
    async def context_precision_score(question, output):
        context_precision_prompt = """Given question, answer and context verify if the context was useful in arriving at the given answer. Give verdict as "1" if useful and "0" if not with json output.
        Output in only valid JSON format.

        question: {question}
        context: {context}
        answer: {answer}
        verdict: """
        client = OpenAI()

        prompt = context_precision_prompt.format(
            question=question,
            context=output['context'],
            answer=output['answer'],
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

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

### Optional: Defining a `Scorer` class

In some applications we want to create custom evaluation classes - where for example a standardized `LLMJudge` class should be created with specific parameters (e.g. chat model, prompt), specific scoring of each row, and specific calculation of an aggregate score. In order to do that Weave defines a list of ready-to-use `Scorer` classes and also makes it easy to create a custom `Scorer` - in the following we'll see how to create a custom `class CorrectnessLLMJudge(Scorer)`.

On a high-level the steps to create custom Scorer are quite simple:

1. Define a custom class that inherits from `weave.flow.scorer.Scorer`
2. Overwrite the `score` function and add a `@weave.op()` if you want to track each call of the function
   - this function has to define an `output` argument where the prediction of the model will be passed to. We define it as type `Optional[dict]` in case the mode might return "None".
   - the rest of the arguments can either be a general `Any` or `dict` or can select specific columns from the dataset that is used to evaluate the model using the `weave.Evaluate` class - they have to have the exact same names as the column names or keys of a single row after being passed to `preprocess_model_input` if that is used.
3. _Optional:_ Overwrite the `summarize` function to customize the calculation of the aggregate score. By default Weave uses the `weave.flow.scorer.auto_summarize` function if you don't define a custom function.
   - this function has to have a `@weave.op()` decorator.

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    from weave.scorers import Scorer
    from weave import WeaveList

    class CorrectnessLLMJudge(Scorer):
        prompt: str
        model_name: str
        device: str

        @weave.op()
        async def score(self, output: Optional[dict], query: str, answer: str) -> Any:
            """Score the correctness of the predictions by comparing the pred, query, target.
            Args:
                - output: the dict that will be provided by the model that is evaluated
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
                    "result": output.get("result"),
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

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

To use this as a scorer, you would initialize it and pass it to `scorers` argument in your `Evaluation like this:

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    evaluation = weave.Evaluation(dataset=questions, scorers=[CorrectnessLLMJudge()])
    ```
  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## 4. Pulling it all together

To get the same result for your RAG apps:

- Wrap LLM calls & retrieval step functions with `weave.op()`
- (optional) Create a `Model` subclass with `predict` function and app details
- Collect examples to evaluate
- Create scoring functions that score one example
- Use `Evaluation` class to run evaluations on your examples

**NOTE:** Sometimes the async execution of Evaluations will trigger a rate limit on the models of OpenAI, Anthropic, etc. To prevent that you can set an environment variable to limit the amount of parallel workers e.g. `WEAVE_PARALLELISM=3`.

Here, we show the code in it's entirety.

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
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
        "Berkshire shares jump after big profit gain as Buffetts conglomerate nears $1 trillion valuation Berkshire Hathaway shares rose on Monday after Warren Buffetts conglomerate posted strong earnings for the fourth quarter over the weekend. Berkshires Class A and B shares jumped more than 1.5%, each. Class A shares are higher by more than 17% this year, while Class B has gained more than 18%. Berkshire was last valued at $930.1 billion, up from $905.5 billion where it closed on Friday, according to FactSet. Berkshire on Saturday posted fourth-quarter operating earnings of $8.481 billion, about 28 percent higher than the $6.625 billion from the year-ago period, driven by big gains in its insurance business. Operating earnings refers to profits from businesses across insurance, railroads and utilities. Meanwhile, Berkshires cash levels also swelled to record levels. The conglomerate held $167.6 billion in cash in the fourth quarter, surpassing the $157.2 billion record the conglomerate held in the prior quarter.",
        "Highmark Health says its combining tech from Google and Epic to give doctors easier access to information Highmark Health announced it is integrating technology from Google Cloud and the health-care software company Epic Systems. The integration aims to make it easier for both payers and providers to access key information they need, even if it's stored across multiple points and formats, the company said. Highmark is the parent company of a health plan with 7 million members, a provider network of 14 hospitals and other entities",
        "Rivian and Lucid shares plunge after weak EV earnings reports Shares of electric vehicle makers Rivian and Lucid fell Thursday after the companies reported stagnant production in their fourth-quarter earnings after the bell Wednesday. Rivian shares sank about 25 percent, and Lucids stock dropped around 17 percent. Rivian forecast it will make 57,000 vehicles in 2024, slightly less than the 57,232 vehicles it produced in 2023. Lucid said it expects to make 9,000 vehicles in 2024, more than the 8,428 vehicles it made in 2023.",
        "Mauritius blocks Norwegian cruise ship over fears of a potential cholera outbreak Local authorities on Sunday denied permission for the Norwegian Dawn ship, which has 2,184 passengers and 1,026 crew on board, to access the Mauritius capital of Port Louis, citing “potential health risks.” The Mauritius Ports Authority said Sunday that samples were taken from at least 15 passengers on board the cruise ship. A spokesperson for the U.S.-headquartered Norwegian Cruise Line Holdings said Sunday that 'a small number of guests experienced mild symptoms of a stomach-related illness' during Norwegian Dawns South Africa voyage.",
        "Intuitive Machines lands on the moon in historic first for a U.S. company Intuitive Machines Nova-C cargo lander, named Odysseus after the mythological Greek hero, is the first U.S. spacecraft to soft land on the lunar surface since 1972. Intuitive Machines is the first company to pull off a moon landing — government agencies have carried out all previously successful missions. The company's stock surged in extended trading Thursday, after falling 11 percent in regular trading.",
        "Lunar landing photos: Intuitive Machines Odysseus sends back first images from the moon Intuitive Machines cargo moon lander Odysseus returned its first images from the surface. Company executives believe the lander caught its landing gear sideways on the surface of the moon while touching down and tipped over. Despite resting on its side, the company's historic IM-1 mission is still operating on the moon.",
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

    # Here is our scoring function uses our question and output to product a score
    # highlight-next-line
    @weave.op()
    # highlight-next-line
    async def context_precision_score(question, output):
        context_precision_prompt = """Given question, answer and context verify if the context was useful in arriving at the given answer. Give verdict as "1" if useful and "0" if not with json output.
        Output in only valid JSON format.

        question: {question}
        context: {context}
        answer: {answer}
        verdict: """
        client = OpenAI()

        prompt = context_precision_prompt.format(
            question=question,
            context=output['context'],
            answer=output['answer'],
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

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## Conclusion

We've learned how to build observability into different steps of our applications, like the retrieval step in this example.
We've also learned how to build more complex scoring functions, like an LLM judge, for doing automatic evaluation of application responses.

```

```</doc><doc title="tutorial-tracing_2">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Track data flows and app metadata

In the [Track LLM inputs & outputs](/quickstart) tutorial, the basics of tracking the inputs and outputs of your LLMs was covered.

In this tutorial you will learn how to:

- **Track data** as it flows through your application
- **Track metadata** at call time

## Tracking nested function calls

LLM-powered applications can contain multiple LLMs calls and additional data processing and validation logic that is important to monitor. Even deep nested call structures common in many apps, Weave will keep track of the parent-child relationships in nested functions as long as `weave.op()` is added to every function you'd like to track.

Building on our [basic tracing example](/quickstart), we will now add additional logic to count the returned items from our LLM and wrap them all in a higher level function. We'll then add `weave.op()` to trace every function, its call order and its parent-child relationship:

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>

    ```python
    import weave
    import json
    from openai import OpenAI

    client = OpenAI(api_key="...")

    # highlight-next-line
    @weave.op()
    def extract_dinos(sentence: str) -> dict:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """Extract any dinosaur `name`, their `common_name`, \
    names and whether its `diet` is a herbivore or carnivore, in JSON format."""
                },
                {
                    "role": "user",
                    "content": sentence
                }
                ],
                response_format={ "type": "json_object" }
            )
        return response.choices[0].message.content

    # highlight-next-line
    @weave.op()
    def count_dinos(dino_data: dict) -> int:
        # count the number of items in the returned list
        k = list(dino_data.keys())[0]
        return len(dino_data[k])

    # highlight-next-line
    @weave.op()
    def dino_tracker(sentence: str) -> dict:
        # extract dinosaurs using a LLM
        dino_data = extract_dinos(sentence)

        # count the number of dinosaurs returned
        dino_data = json.loads(dino_data)
        n_dinos = count_dinos(dino_data)
        return {"n_dinosaurs": n_dinos, "dinosaurs": dino_data}

    # highlight-next-line
    weave.init('jurassic-park')

    sentence = """I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike), \
    both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant \
    Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below."""

    result = dino_tracker(sentence)
    print(result)
    ```
    **Nested functions**

    When you run the above code you will see the the inputs and outputs from the two nested functions (`extract_dinos` and `count_dinos`), as well as the automatically-logged OpenAI trace.

    ![Nested Weave Trace](../static/img/tutorial_tracing_2_nested_dinos.png)

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    ```typescript
    import OpenAI from 'openai';
    import * as weave from 'weave';

    const openai = weave.wrapOpenAI(new OpenAI());

    const extractDinos = weave.op(async (sentence: string) => {
      const response = await openai.chat.completions.create({
        model: 'gpt-4o',
        messages: [
          {
            role: 'system',
            content:
              'Extract any dinosaur `name`, their `common_name`, names and whether its `diet` is a herbivore or carnivore, in JSON format.',
          },
          {role: 'user', content: sentence},
        ],
        response_format: {type: 'json_object'},
      });
      return response.choices[0].message.content;
    });

    const countDinos = weave.op(async (dinoData: string) => {
      const parsed = JSON.parse(dinoData);
      return Object.keys(parsed).length;
    });

    const dinoTracker = weave.op(async (sentence: string) => {
      const dinoData = await extractDinos(sentence);
      const nDinos = await countDinos(dinoData);
      return {nDinos, dinoData};
    });

    async function main() {
      await weave.init('jurassic-park');

      const sentence = `I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike),
            both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant
            Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below.`;

      const result = await dinoTracker(sentence);
      console.log(result);
    }

    main();

    ```

    **Nested functions**

    When you run the above code you will see the the inputs and outputs from the two nested functions (`extractDinos` and `countDinos`), as well as the automatically-logged OpenAI trace.

    <!-- TODO: Update to TS screenshot -->
    ![Nested Weave Trace](../static/img/tutorial_tracing_2_nested_dinos.png)

  </TabItem>
</Tabs>

## Tracking metadata

Tracking metadata can be done easily by using the `weave.attributes` context manager and passing it a dictionary of the metadata to track at call time.

Continuing our example from above:

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    import weave

    weave.init('jurassic-park')

    sentence = """I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike), \
    both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant \
    Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below."""

    # track metadata alongside our previously defined function
    # highlight-next-line
    with weave.attributes({'user_id': 'lukas', 'env': 'production'}):
        result = dino_tracker(sentence)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

:::note
It's recommended to use metadata tracking to track metadata at run time, e.g. user ids or whether or not the call is part of the development process or is in production etc.

To track system attributes, such as a System Prompt, we recommend using [weave Models](guides/core-types/models)
:::

## What's next?

- Follow the [App Versioning tutorial](/tutorial-weave_models) to capture, version and organize ad-hoc prompt, model, and application changes.</doc><doc title="tutorial-weave_models">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# App versioning

Tracking the [inputs, outputs, metadata](/quickstart) as well as [data flowing through your app](/tutorial-tracing_2) is critical to understanding the performance of your system. However **versioning your app over time** is also critical to understand how modifications to your code or app attributes change your outputs. Weave's `Model` class is how these changes can be tracked in Weave.

In this tutorial you'll learn:

- How to use Weave `Model` to track and version your app and its attributes.
- How to export, modify and re-use a Weave `Model` already logged.

## Using `weave.Model`

:::warning

The `weave.Model` class is currently only supported in Python!

:::

Using Weave `Model`s means that attributes such as model vendor ids, prompts, temperature, and more are stored and versioned when they change.

To create a `Model` in Weave, you need the following:

- a class that inherits from `weave.Model`
- type definitions on all class attributes
- a typed `invoke` function with the `@weave.op()` decorator

When you change the class attributes or the code that defines your model, **these changes will be logged and the version will be updated**. This ensures that you can compare the generations across different versions of your app.

In the example below, the **model name, temperature and system prompt will be tracked and versioned**:

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    import json
    from openai import OpenAI

    import weave

    @weave.op()
    def extract_dinos(wmodel: weave.Model, sentence: str) -> dict:
        response = wmodel.client.chat.completions.create(
            model=wmodel.model_name,
            temperature=wmodel.temperature,
            messages=[
                {
                    "role": "system",
                    "content": wmodel.system_prompt
                },
                {
                    "role": "user",
                    "content": sentence
                }
                ],
                response_format={ "type": "json_object" }
            )
        return response.choices[0].message.content

    # Sub-class with a weave.Model
    # highlight-next-line
    class ExtractDinos(weave.Model):
        client: OpenAI = None
        model_name: str
        temperature: float
        system_prompt: str

        # Ensure your function is called `invoke` or `predict`
        # highlight-next-line
        @weave.op()
        # highlight-next-line
        def invoke(self, sentence: str) -> dict:
            dino_data  = extract_dinos(self, sentence)
            return json.loads(dino_data)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

Now you can instantiate and call the model with `invoke`:

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    weave.init('jurassic-park')
    client = OpenAI()

    system_prompt = """Extract any dinosaur `name`, their `common_name`, \
    names and whether its `diet` is a herbivore or carnivore, in JSON format."""

    # highlight-next-line
    dinos = ExtractDinos(
        client=client,
        model_name='gpt-4o',
        temperature=0.4,
        system_prompt=system_prompt
    )

    sentence = """I watched as a Tyrannosaurus rex (T. rex) chased after a Triceratops (Trike), \
    both carnivore and herbivore locked in an ancient dance. Meanwhile, a gentle giant \
    Brachiosaurus (Brachi) calmly munched on treetops, blissfully unaware of the chaos below."""

    # highlight-next-line
    result = dinos.invoke(sentence)
    print(result)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

Now after calling `.invoke` you can see the trace in Weave **now tracks the model attributes as well as the code** for the model functions that have been decorated with `weave.op()`. You can see the model is also versioned, "v21" in this case, and if you click on the model **you can see all of the calls** that have used that version of the model

![Re-using a weave model](../static/img/tutorial-model_invoke3.png)

**A note on using `weave.Model`:**

- You can use `predict` instead of `invoke` for the name of the function in your Weave `Model` if you prefer.
- If you want other class methods to be tracked by weave they need to be wrapped in `weave.op()`
- Attributes starting with an underscore are ignored by weave and won't be logged

## Exporting and re-using a logged `weave.Model`

Because Weave stores and versions Models that have been invoked, it is possible to export and re-use these models.

**Get the Model ref**
In the Weave UI you can get the Model ref for a particular version

**Using the Model**
Once you have the URI of the Model object, you can export and re-use it. Note that the exported model is already initialised and ready to use:

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    # the exported weave model is already initialised and ready to be called
    # highlight-next-line
    new_dinos = weave.ref("weave:///morgan/jurassic-park/object/ExtractDinos:ey4udBU2MU23heQFJenkVxLBX4bmDsFk7vsGcOWPjY4").get()

    # set the client to the openai client again
    new_dinos.client = client

    new_sentence = """I also saw an Ankylosaurus grazing on giant ferns"""
    new_result = new_dinos.invoke(new_sentence)
    print(new_result)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

Here you can now see the name Model version (v21) was used with the new input:

![Re-using a weave model](../static/img/tutorial-model_re-use.png)

## What's next?

- Follow the [Build an Evaluation pipeline tutorial](/tutorial-eval) to start iteratively improving your applications.</doc><doc title="costs">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Costs

## Adding a custom cost

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    You can add a custom cost by using the [`add_cost`](/reference/python-sdk/weave/trace/weave.trace.weave_client#method-add_cost) method.
    The three required fields are `llm_id`, `prompt_token_cost`, and `completion_token_cost`.
    `llm_id` is the name of the LLM (e.g. `gpt-4o`). `prompt_token_cost` and `completion_token_cost` are cost per token for the LLM (if the LLM prices were specified inper million tokens, make sure to convert the value).
    You can also set `effective_date` to a datetime, to make the cost effective at a specific date, this defaults to the current date.

    ```python
    import weave
    from datetime import datetime

    client = weave.init("my_custom_cost_model")

    client.add_cost(
        llm_id="your_model_name",
        prompt_token_cost=0.01,
        completion_token_cost=0.02
    )

    client.add_costs(
        llm_id="your_model_name",
        prompt_token_cost=10,
        completion_token_cost=20,
        # If for example I want to raise the price of the model after a certain date
        effective_date=datetime(2025, 4, 22),
    )
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```

  </TabItem>
</Tabs>

## Querying for costs

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    You can query for costs by using the [`query_costs`](/reference/python-sdk/weave/trace/weave.trace.weave_client#method-query_costs) method.
    There are a few ways to query for costs, you can pass in a singular cost id, or a list of LLM model names.

    ```python
    import weave

    client = weave.init("my_custom_cost_model")

    costs = client.query_costs(llm_ids=["your_model_name"])

    cost = client.query_costs(costs[0].id)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```

  </TabItem>
</Tabs>

## Purging a custom cost

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    You can purge a custom cost by using the [`purge_costs`](/reference/python-sdk/weave/trace/weave.trace.weave_client#method-purge_costs) method. You pass in a list of cost ids, and the costs with those ids are purged.

    ```python
    import weave

    client = weave.init("my_custom_cost_model")

    costs = client.query_costs(llm_ids=["your_model_name"])
    client.purge_costs([cost.id for cost in costs])
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## Calculating costs for a Project

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    You can calculate costs for a project by using our `calls_query` and adding `include_costs=True` with a little bit of setup.

    ```python
    import weave

    weave.init("project_costs")
    @weave.op()
    def get_costs_for_project(project_name: str):
        total_cost = 0
        requests = 0

        client = weave.init(project_name)
        # Fetch all the calls in the project
        calls = list(
            client.get_calls(filter={"trace_roots_only": True}, include_costs=True)
        )

        for call in calls:
            # If the call has costs, we add them to the total cost
            if call.summary["weave"] is not None and call.summary["weave"].get("costs", None) is not None:
                for k, cost in call.summary["weave"]["costs"].items():
                    requests += cost["requests"]
                    total_cost += cost["prompt_tokens_total_cost"]
                    total_cost += cost["completion_tokens_total_cost"]

        # We return the total cost, requests, and calls
        return {
            "total_cost": total_cost,
            "requests": requests,
            "calls": len(calls),
        }

    # Since we decorated our function with @weave.op(),
    # our totals are stored in weave for historic cost total calculations
    get_costs_for_project("my_custom_cost_model")
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## Setting up a custom model with custom costs

Try our cookbook for a [Setting up costs with a custom model](/reference/gen_notebooks/custom_model_cost) or <a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/custom_model_cost.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a></doc><doc title="datasets">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Datasets

`Dataset`s enable you to collect examples for evaluation and automatically track versions for accurate comparisons. Use this to download the latest version locally with a simple API.

This guide will show you how to:

- Publish `Dataset`s to W&B
- Download the latest version
- Iterate over examples

## Sample code

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    import weave
    from weave import Dataset
    # Initialize Weave
    weave.init('intro-example')

    # Create a dataset
    dataset = Dataset(
        name='grammar',
        rows=[
            {'id': '0', 'sentence': "He no likes ice cream.", 'correction': "He doesn't like ice cream."},
            {'id': '1', 'sentence': "She goed to the store.", 'correction': "She went to the store."},
            {'id': '2', 'sentence': "They plays video games all day.", 'correction': "They play video games all day."}
        ]
    )

    # Publish the dataset
    weave.publish(dataset)

    # Retrieve the dataset
    dataset_ref = weave.ref('grammar').get()

    # Access a specific example
    example_label = dataset_ref.rows[2]['sentence']
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```typescript
    import * as weave from 'weave';

    // Initialize Weave
    await weave.init('intro-example');

    // Create a dataset
    const dataset = new weave.Dataset({
        name: 'grammar',
        rows: [
            {id: '0', sentence: "He no likes ice cream.", correction: "He doesn't like ice cream."},
            {id: '1', sentence: "She goed to the store.", correction: "She went to the store."},
            {id: '2', sentence: "They plays video games all day.", correction: "They play video games all day."}
        ]
    });

    // Publish the dataset
    await dataset.save();

    // Access a specific example
    const exampleLabel = datasetRef.getRow(2).sentence;
    ```

  </TabItem>
</Tabs></doc><doc title="deploy"># Deploy

## Deploy to GCP

:::note
`weave deploy` requires your machine to have `gcloud` installed and configured. `weave deploy gcp` will use pre-configured configuration when not directly specified by command line arguments.
:::

Given a Weave ref to any Weave Model you can run:

```
weave deploy gcp <ref>
```

to deploy a gcp cloud function that serves your model. The last line of the deployment will look like `Service URL: <PATH_TO_MODEL>`. Visit `<PATH_TO_MODEL>/docs` to interact with your model!

Run

```
weave deploy gcp --help
```

to see all command line options.</doc><doc title="evaluations"># Evaluations

Evaluation-driven development helps you reliably iterate on an application. The `Evaluation` class is designed to assess the performance of a `Model` on a given `Dataset` or set of examples using scoring functions.

![Evals hero](../../../static/img/evals-hero.png)

```python
import weave
from weave import Evaluation
import asyncio

# Collect your examples
examples = [
    {"question": "What is the capital of France?", "expected": "Paris"},
    {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
    {"question": "What is the square root of 64?", "expected": "8"},
]

# Define any custom scoring function
@weave.op()
def match_score1(expected: str, model_output: dict) -> dict:
    # Here is where you'd define the logic to score the model output
    return {'match': expected == model_output['generated_text']}

@weave.op()
def function_to_evaluate(question: str):
    # here's where you would add your LLM call and return the output
    return  {'generated_text': 'Paris'}

# Score your examples using scoring functions
evaluation = Evaluation(
    dataset=examples, scorers=[match_score1]
)

# Start tracking the evaluation
weave.init('intro-example')
# Run the evaluation
asyncio.run(evaluation.evaluate(function_to_evaluate))
```

## Create an Evaluation

To systematically improve your application, it's helpful to test your changes against a consistent dataset of potential inputs so that you catch regressions and can inspect your apps behaviour under different conditions. Using the `Evaluation` class, you can be sure you're comparing apples-to-apples by keeping track of all of the details that you're experimenting and evaluating with.

Weave will take each example, pass it through your application and score the output on multiple custom scoring functions. By doing this, you'll have a view of the performance of your application, and a rich UI to drill into individual outputs and scores.

### Define an evaluation dataset

First, define a [Dataset](/guides/core-types/datasets) or list of dictionaries with a collection of examples to be evaluated. These examples are often failure cases that you want to test for, these are similar to unit tests in Test-Driven Development (TDD).

### Defining scoring functions

Then, create a list of scoring functions. These are used to score each example. Each function should have a `model_output` and optionally, other inputs from your examples, and return a dictionary with the scores.

Scoring functions need to have a `model_output` keyword argument, but the other arguments are user defined and are taken from the dataset examples. It will only take the necessary keys by using a dictionary key based on the argument name.

This will take `expected` from the dictionary for scoring.

```python
import weave

# Collect your examples
examples = [
    {"question": "What is the capital of France?", "expected": "Paris"},
    {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
    {"question": "What is the square root of 64?", "expected": "8"},
]

# Define any custom scoring function
@weave.op()
def match_score1(expected: str, model_output: dict) -> dict:
    # Here is where you'd define the logic to score the model output
    return {'match': expected == model_output['generated_text']}
```

### Optional: Define a custom `Scorer` class

In some applications we want to create custom `Scorer` classes - where for example a standardized `LLMJudge` class should be created with specific parameters (e.g. chat model, prompt), specific scoring of each row, and specific calculation of an aggregate score.

See the tutorial on defining a `Scorer` class in the next chapter on [Model-Based Evaluation of RAG applications](/tutorial-rag#optional-defining-a-scorer-class) for more information.

### Define a Model to evaluate

To evaluate a `Model`, call `evaluate` on it using an `Evaluation`. `Models` are used when you have attributes that you want to experiment with and capture in weave.

```python
from weave import Model, Evaluation
import asyncio

class MyModel(Model):
    prompt: str

    @weave.op()
    def predict(self, question: str):
        # here's where you would add your LLM call and return the output
        return {'generated_text': 'Hello, ' + self.prompt}

model = MyModel(prompt='World')

evaluation = Evaluation(
    dataset=examples, scorers=[match_score1]
)
weave.init('intro-example') # begin tracking results with weave
asyncio.run(evaluation.evaluate(model))
```

This will run `predict` on each example and score the output with each scoring functions.

#### Custom Naming

You can change the name of the Evaluation itself by passing a `name` parameter to the `Evaluation` class.

```python
evaluation = Evaluation(
    dataset=examples, scorers=[match_score1], name="My Evaluation"
)
```

You can also change the name of individual evaluations by setting the `display_name` key of the `__weave` dictionary.

:::note

Using the `__weave` dictionary sets the call display name which is distinct from the Evaluation object name. In the
UI, you will see the display name if set, otherwise the Evaluation object name will be used.

:::

```python
evaluation = Evaluation(
    dataset=examples, scorers=[match_score1]
)
evaluation.evaluate(model, __weave={"display_name": "My Evaluation Run"})
```

### Define a function to evaluate

Alternatively, you can also evaluate a function that is wrapped in a `@weave.op()`.

```python
@weave.op()
def function_to_evaluate(question: str):
    # here's where you would add your LLM call and return the output
    return  {'generated_text': 'some response'}

asyncio.run(evaluation.evaluate(function_to_evaluate))
```

### Pulling it all together

```python
from weave import Evaluation, Model
import weave
import asyncio
weave.init('intro-example')
examples = [
    {"question": "What is the capital of France?", "expected": "Paris"},
    {"question": "Who wrote 'To Kill a Mockingbird'?", "expected": "Harper Lee"},
    {"question": "What is the square root of 64?", "expected": "8"},
]

@weave.op()
def match_score1(expected: str, model_output: dict) -> dict:
    return {'match': expected == model_output['generated_text']}

@weave.op()
def match_score2(expected: dict, model_output: dict) -> dict:
    return {'match': expected == model_output['generated_text']}

class MyModel(Model):
    prompt: str

    @weave.op()
    def predict(self, question: str):
        # here's where you would add your LLM call and return the output
        return {'generated_text': 'Hello, ' + question + self.prompt}

model = MyModel(prompt='World')
evaluation = Evaluation(dataset=examples, scorers=[match_score1, match_score2])

asyncio.run(evaluation.evaluate(model))

@weave.op()
def function_to_evaluate(question: str):
    # here's where you would add your LLM call and return the output
    return  {'generated_text': 'some response' + question}

asyncio.run(evaluation.evaluate(function_to_evaluate))
```</doc><doc title="feedback">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Feedback

Evaluating LLM applications automatically is challenging. Teams often rely on direct user feedback, particularly from domain experts, who assess the content quality using simple indicators such as thumbs up or down. Developers also actively identify and resolve content issues.

Weave's feedback feature enables users to provide feedback directly within the Weave UI or through the API. You can add emoji reactions, textual notes, and structured data to calls. This feedback helps compile evaluation datasets, monitor application performance, and collect examples for advanced tasks like fine-tuning.

## View and Add Feedback within UI

Reactions and notes are displayed in a column in the calls grid. Hovering over these indicators provides more detail. Use these buttons to add reactions or notes.

![Screenshot of calls grid with feedback column](imgs/feedback_calls.png)

View and edit feedback in the header of the call details page.

![Screenshot of feedback controls in call details header](imgs/feedback_call_header.png)

View the feedback for a call on the "Feedback" tab of the call details page.

![Screenshot of Feedback tab in call details](imgs/feedback_tab.png)

Access copy-and-paste examples on the "Use" tab of the call details page to manipulate the feedback for that call using the SDK.

![Screenshot of Use tab in call details](imgs/feedback_use.png)

## SDK

Use the Weave SDK to programmatically add, remove, and query feedback on calls.

### Querying a project's feedback

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    import weave
    client = weave.init('intro-example')

    # Get all feedback in a project
    all_feedback = client.get_feedback()

    # Fetch a specific feedback object by id.
    # Note that the API still returns a collection, which is expected
    # to contain zero or one item(s).
    one_feedback = client.get_feedback("<feedback_uuid>")[0]

    # Find all feedback objects with a specific reaction. You can specify offset and limit.
    thumbs_up = client.get_feedback(reaction="👍", limit=10)

    # After retrieval you can view the details of individual feedback objects.
    for f in client.get_feedback():
        print(f.id)
        print(f.created_at)
        print(f.feedback_type)
        print(f.payload)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

### Adding feedback to a call

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    import weave
    client = weave.init('intro-example')

    call = client.get_call("<call_uuid>")

    # Adding an emoji reaction
    call.feedback.add_reaction("👍")

    # Adding a note
    call.feedback.add_note("this is a note")

    # Adding custom key/value pairs.
    # The first argument is a user-defined "type" string.
    # Feedback must be JSON serializable and less than 1kb when serialized.
    call.feedback.add("correctness", { "value": 5 })
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

### Retrieving the Call UUID

For scenarios where you need to add feedback immediately after a call, you can retrieve the call UUID programmatically during or after the call execution. Here is how to get the UUID of the call from within the operation:

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python

    import weave
    weave.init("uuid")

    @weave.op()
    def simple_operation(input_value):
        # Perform some simple operation
        output = f"Processed {input_value}"
        # Get the current call ID
        current_call = weave.require_current_call()
        call_id = current_call.id
        return output, call_id
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

Additionally, you can use call() method to execute the operation and retrieve the call ID after execution of the function:

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    import weave
    weave.init("uuid")

    @weave.op()
    def simple_operation(input_value):
        return f"Processed {input_value}"

    # Execute the operation and retrieve the result and call ID
    result, call = simple_operation.call("example input")
    call_id = call.id
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

### Querying feedback on a call

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    for f in call.feedback:
        print(f.id)
        print(f.feedback_type)
        print(f.payload)
    ```
  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

### Deleting feedback from a call

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    ```python
    call.feedback.purge("<feedback_uuid>")
    ```
  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs></doc><doc title="media">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Logging media

Weave supports logging and displaying multiple first class media types. Log images with `PIL.Image.Image` and audio with `wave.Wave_read` either directly with the object API, or as the inputs or output of an op.

## Images

Logging type: `PIL.Image.Image`. Here is an example of logging an image with the OpenAI DALL-E API:

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
  
    ```python
    import weave
    from openai import OpenAI
    import requests
    from PIL import Image

    weave.init('image-example')
    client = OpenAI()

    @weave.op
    def generate_image(prompt: str) -> Image:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        image_response = requests.get(image_url, stream=True)
        image = Image.open(image_response.raw)

        # return a PIL.Image.Image object to be logged as an image
        return image

    generate_image("a cat with a pumpkin hat")
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    ```typescript
    import {OpenAI} from 'openai';
    import * as weave from 'weave';

    async function main() {
        const client = await weave.init('image-example');
        const openai = new OpenAI();

        const generateImage = weave.op(async (prompt: string) => {
            const response = await openai.images.generate({
                model: 'dall-e-3',
                prompt: prompt,
                size: '1024x1024',
                quality: 'standard',
                n: 1,
            });
            const imageUrl = response.data[0].url;
            const imgResponse = await fetch(imageUrl);
            const data = Buffer.from(await imgResponse.arrayBuffer());

            return weave.weaveImage({data});
        });

        generateImage('a cat with a pumpkin hat');
    }

    main();
    ```

  </TabItem>
</Tabs>

This image will be logged to weave and automatically displayed in the UI. The following is the trace view for above.

![Screenshot of pumpkin cat trace view](imgs/cat-pumpkin-trace.png)

## Audio

Logging type: `wave.Wave_read`. Here is an example of logging an audio file using openai's speech generation API.

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
  
    ```python
    import weave
    from openai import OpenAI
    import wave

    weave.init("audio-example")
    client = OpenAI()


    @weave.op
    def make_audio_file_streaming(text: str) -> wave.Wave_read:
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice="alloy",
            input=text,
            response_format="wav",
        ) as res:
            res.stream_to_file("output.wav")

        # return a wave.Wave_read object to be logged as audio
        return wave.open("output.wav")

    make_audio_file_streaming("Hello, how are you?")
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">

    ```typescript
    import {OpenAI} from 'openai';
    import * as weave from 'weave';

    async function main() {
        await weave.init('audio-example');
        const openai = new OpenAI();

        const makeAudioFileStreaming = weave.op(async function audio(text: string) {
            const response = await openai.audio.speech.create({
                model: 'tts-1',
                voice: 'alloy',
                input: text,
                response_format: 'wav',
            });

            const chunks: Uint8Array[] = [];
            for await (const chunk of response.body) {
                chunks.push(chunk);
            }
            return weave.weaveAudio({data: Buffer.concat(chunks)});
        });

        await makeAudioFileStreaming('Hello, how are you?');
    }

    main();
    ```

  </TabItem>
</Tabs>

This audio will be logged to weave and automatically displayed in the UI, with an audio player. The player can be expanded to view the raw audio waveform, in addition to a download button.

![Screenshot of audio trace view](imgs/audio-trace.png)

Try our cookbook for [Audio Logging](/reference/gen_notebooks/audio_with_weave) or <a href="https://colab.research.google.com/github/wandb/weave/blob/master/docs/./notebooks/audio_with_weave.ipynb" target="_blank" rel="noopener noreferrer" class="navbar__item navbar__link button button--secondary button--med margin-right--sm notebook-cta-button"><div><img src="https://upload.wikimedia.org/wikipedia/commons/archive/d/d0/20221103151430%21Google_Colaboratory_SVG_Logo.svg" alt="Open In Colab" height="20px" /><div>Open in Colab</div></div></a>. The cookbook also includes an advanced example of a Real Time Audio API based assistant integrated with Weave.</doc><doc title="models">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Models

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    A `Model` is a combination of data (which can include configuration, trained model weights, or other information) and code that defines how the model operates. By structuring your code to be compatible with this API, you benefit from a structured way to version your application so you can more systematically keep track of your experiments.

    To create a model in Weave, you need the following:

    - a class that inherits from `weave.Model`
    - type definitions on all attributes
    - a typed `predict` function with `@weave.op()` decorator

    ```python
    from weave import Model
    import weave

    class YourModel(Model):
        attribute1: str
        attribute2: int

        @weave.op()
        def predict(self, input_data: str) -> dict:
            # Model logic goes here
            prediction = self.attribute1 + ' ' + input_data
            return {'pred': prediction}
    ```

    You can call the model as usual with:

    ```python
    import weave
    weave.init('intro-example')

    model = YourModel(attribute1='hello', attribute2=5)
    model.predict('world')
    ```

    This will track the model settings along with the inputs and outputs anytime you call `predict`.

    ## Automatic versioning of models

    When you change the attributes or the code that defines your model, these changes will be logged and the version will be updated.
    This ensures that you can compare the predictions across different versions of your model. Use this to iterate on prompts or to try the latest LLM and compare predictions across different settings.

    For example, here we create a new model:

    ```python
    import weave
    weave.init('intro-example')

    model = YourModel(attribute1='howdy', attribute2=10)
    model.predict('world')
    ```

    After calling this, you will see that you now have two versions of this Model in the UI, each with different tracked calls.

    ## Serve models

    To serve a model, you can easily spin up a FastAPI server by calling:

    ```bash
    weave serve <your model ref>
    ```

    For additional instructions, see [serve](/guides/tools/serve).

    ## Track production calls

    To separate production calls, you can add an additional attribute to the predictions for easy filtering in the UI or API.

    ```python
    with weave.attributes({'env': 'production'}):
        model.predict('world')
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs></doc><doc title="objects">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Objects

## Publishing an object

Weave's serialization layer saves and versions objects.

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>

    ```python
    import weave
    # Initialize tracking to the project 'intro-example'
    weave.init('intro-example')
    # Save a list, giving it the name 'cat-names'
    weave.publish(['felix', 'jimbo', 'billie'], 'cat-names')
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    Publishing in TypeScript is still early, so not all objects are fully supported yet.

    ```typescript
    import * as weave from 'weave'

    // Initialize tracking to the project 'intro-example'
    const client = await weave.init('intro-example')

    // Save an array, giving it the name 'cat-names'
    client.publish(['felix', 'jimbo', 'billie'], 'cat-names')
    ```

  </TabItem>
</Tabs>

Saving an object with a name will create the first version of that object if it doesn't exist.

## Getting an object back

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    `weave.publish` returns a Ref. You can call `.get()` on any Ref to get the object back.

    You can construct a ref and then fetch the object back.

    ```python
    weave.init('intro-example')
    cat_names = weave.ref('cat-names').get()
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## Ref styles

A fully qualified weave object ref uri looks like this:

```
weave:///<entity>/<project>/object/<object_name>:<object_version>
```

- _entity_: wandb entity (username or team)
- _project_: wandb project
- _object_name_: object name
- _object_version_: either a version hash, a string like v0, v1..., or an alias like ":latest". All objects have the ":latest" alias.

Refs can be constructed with a few different styles

- `weave.ref(<name>)`: requires `weave.init(<project>)` to have been called. Refers to the ":latest" version
- `weave.ref(<name>:<version>)`: requires `weave.init(<project>)` to have been called.
- `weave.ref(<fully_qualified_ref_uri>)`: can be constructed without calling weave.init</doc><doc title="ops">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Ops

A Weave op is a versioned function that automatically logs all calls.

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    To create an op, decorate a python function with `weave.op()`

    ```python showLineNumbers
    import weave

    @weave.op()
    def track_me(v):
        return v + 5

    weave.init('intro-example')
    track_me(15)
    ```

    Calling an op will create a new op version if the code has changed from the last call, and log the inputs and outputs of the function.

    :::note
    Functions decorated with `@weave.op()` will behave normally (without code versioning and tracking), if you don't call `weave.init('your-project-name')` before calling them.
    :::

    Ops can be [served](/guides/tools/serve) or [deployed](/guides/tools/deploy) using the Weave toolbelt.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    To create an op, wrap a typescript function with `weave.op`

    ```typescript showLineNumbers
    import * as weave from 'weave'

    function trackMe(v: number) {
        return v + 5
    }

    const trackMeOp = weave.op(trackMe)
    trackMeOp(15)


    // You can also do this inline, which may be more convenient
    const trackMeInline = weave.op((v: number) => v + 5)
    trackMeInline(15)
    ```

  </TabItem>
</Tabs>

## Customize display names

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    You can customize the op's display name by setting the `name` parameter in the `@weave.op` decorator:

    ```python
    @weave.op(name="custom_name")
    def func():
        ...
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## Customize logged inputs and outputs

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    If you want to change the data that is logged to weave without modifying the original function (e.g. to hide sensitive data), you can pass `postprocess_inputs` and `postprocess_output` to the op decorator.

    `postprocess_inputs` takes in a dict where the keys are the argument names and the values are the argument values, and returns a dict with the transformed inputs.

    `postprocess_output` takes in any value which would normally be returned by the function and returns the transformed output.

    ```py
    from dataclasses import dataclass
    from typing import Any
    import weave

    @dataclass
    class CustomObject:
        x: int
        secret_password: str

    def postprocess_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
        return {k:v for k,v in inputs.items() if k != "hide_me"}

    def postprocess_output(output: CustomObject) -> CustomObject:
        return CustomObject(x=output.x, secret_password="REDACTED")

    @weave.op(
        postprocess_inputs=postprocess_inputs,
        postprocess_output=postprocess_output,
    )
    def func(a: int, hide_me: str) -> CustomObject:
        return CustomObject(x=a, secret_password=hide_me)

    weave.init('hide-data-example') # 🐝
    func(a=1, hide_me="password123")
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

### Control call link output 

If you want to suppress the printing of call links during logging, you can use the `WEAVE_PRINT_CALL_LINK` environment variable to `false`. This can be useful if you want to reduce  output verbosity and reduce clutter in your logs.

```bash
export WEAVE_PRINT_CALL_LINK=false
```</doc><doc title="platform"># Platform & Security

Weave is available on [W&B SaaS Cloud](https://docs.wandb.ai/guides/hosting/hosting-options/saas_cloud) which is a multi-tenant, fully-managed platform deployed in W&B's Google Cloud Platform (GCP) account in a North America region.

:::info
It's coming soon on [W&B Dedicated Cloud](https://docs.wandb.ai/guides/hosting/hosting-options/dedicated_cloud). Reach out to your W&B team if that would be of interest in your organization.
:::

## Identity & Access Management

Use the identity and access management capabilities for secure authentication and effective authorization in your [W&B Organization](https://docs.wandb.ai/guides/hosting/iam/org_team_struct#organization). The following capabilities are available for Weave users in W&B SaaS Cloud:

* Authenticate using Single-Sign On (SSO), with available options being Google, Github, Microsoft, and [OIDC providers](https://docs.wandb.ai/guides/technical-faq/general#does-wb-support-sso-for-saas)
* [Team-based access control](https://docs.wandb.ai/guides/hosting/iam/manage-users#manage-a-team), where each team may correspond to a business unit / function, department, or a project team in your company
* Use W&B projects to organize different initiatives within a team, and configure the required [visibility scope](https://docs.wandb.ai/guides/hosting/restricted-projects) for each project

## Data Security

In the W&B SaaS Cloud, data of all Weave users is stored in a shared cloud storage and is processed using shared compute services. The shared cloud storage is encrypted using the cloud-native encryption mechanism. When reading or writing data on behalf of a user, a security context comprising of the user's W&B organization, team and project is utilized to ensure data path isolation.

:::note
[Secure storage connector](https://docs.wandb.ai/guides/hosting/secure-storage-connector) is not applicable to Weave.
:::

## Maintenance

If you're using Weave on W&B SaaS Cloud, you do not incur the overhead and costs of provisioning and maintaining the W&B platform. It's all fully managed for you.

## Compliance

Security controls for W&B SaaS Cloud are periodically audited internally and externally. Refer to the [W&B Security Portal](https://security.wandb.ai/) to request the SOC2 report and other security and compliance documents.</doc><doc title="prod_dashboard">---
sidebar_position: 2
hide_table_of_contents: true
---

# Integrating with Weave: Case Study - Custom Dashboard for Production Monitoring
When we consider how well Weave can be intergated in existing processes and AI Apps we consider data input and data output as the two fundemantal characteristics:
1.  **Data Input:** 
    * **Framework Agnostic Tracing:** Many different tools, packages, frameworks are used to create LLM apps (LangChain, LangGraph, LlamaIndex, AutoGen, CrewAI). Weave's single `@weave-op()` decorator makes it very easy to integrate with any framework and custom objects (THERE SHOULD BE A COOKBOOK FOR HOW TO INTEGRATE AND HOW TO DEAL WITH CUSTOM OBJECTS INCL. SERIALIZATION). For most common frameworks our team already did that making the tracking of apps as easy as initializing Weave before the start of the application. For how feedback can be flexibly integrated into Weave check out the Cookbook Series on Feedback (ADD LINK TO OTHER COOKBOOK HERE).
    * **Openning API endpoints (soon):** LLM applications are very diverse (webpage in typescript, python scripts, java backends, on-device apps) but should still be trckable and traceable from anywhere. For most use-cases Weave is already proving native support (python and typescript coming soon), for the rest Weave makes it very easy to log traces or connect with existing tools (ONE AVAILABLE A COOKBOOK SHOULD BE LAUNCHED ONCE THE NEW APIs ARE EXPOSED).

2. **Data Output**: Weave focuses on a) online monitoring (tracing generations, tracking governance metrics such as cost, latency, tokens) and b) offline evaluations (systematic benchmarking on eval datasets, human feedback loops, LLM judges, side-by-side comparisons). For both parts Weave provides strong visulalization capabiltities through the Weave UI. Sometimes, creating a visual extension based on the specific business or monitoring requirements makes sense - this is what we'll discover in this cookbook (SEEMS LIKE IN THE FUTURE WE'LL HAVE WEAVE BOARDS BACK FOR THAT).

The introduction, specific use-case that we consider in this cookbook:
* In  this cookbook we show how Weave's exposed APIs and functions make it very easy to create a custom dashboard for production monitoring as an extension to the Traces view in Weave. 
* We will focus on creating aggregate views of the cost, latency, tokens, and provided user-feedback
* We will focus on providing aggregation functions across models, calls, and projects
* We will take a look at how to add alerts and guardrailes (GOOD FOR OTHER COOKBOOKS)</doc><doc title="prompts"># Prompts

Creating, evaluating, and refining prompts is a core activity for AI engineers.
Small changes to a prompt can have big impacts on your application's behavior.
Weave lets you create prompts, save and retrieve them, and evolve them over time.

Weave is unopinionated about how a Prompt is constructed. If your needs are simple you can use our built-in `weave.StringPrompt` or `weave.MessagesPrompt` classes. If your needs are more complex you can subclass those or our base class `weave.Prompt` and override the
`format` method.

When you publish one of these objects with `weave.publish`, it will appear in your Weave project on the "Prompts" page.

## StringPrompt

```python
import weave
weave.init('intro-example')

# highlight-next-line
system_prompt = weave.StringPrompt("You are a pirate")
# highlight-next-line
weave.publish(system_prompt, name="pirate_prompt")

from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
  model="gpt-4o",
  messages=[
    {
      "role": "system",
      # highlight-next-line
      "content": system_prompt.format()
    },
    {
      "role": "user",
      "content": "Explain general relativity in one paragraph."
    }
  ],
)
```

Perhaps this prompt does not yield the desired effect, so we modify the prompt to be more
clearly instructive.

```python
import weave
weave.init('intro-example')

# highlight-next-line
system_prompt = weave.StringPrompt("Talk like a pirate. I need to know I'm listening to a pirate.")
weave.publish(system_prompt, name="pirate_prompt")

from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
  model="gpt-4o",
  messages=[
    {
      "role": "system",
      # highlight-next-line
      "content": system_prompt.format()
    },
    {
      "role": "user",
      "content": "Explain general relativity in one paragraph."
    }
  ],
)
```

When viewing this prompt object, I can see that it has two versions.

![Screenshot of viewing a prompt object](imgs/prompt-object.png)

I can also select them for comparison to see exactly what changed.

![Screenshot of prompt comparison](imgs/prompt-comparison.png)

## MessagesPrompt

The `MessagesPrompt` can be used to replace an array of Message objects.

```python
import weave
weave.init('intro-example')

# highlight-next-line
prompt = weave.MessagesPrompt([
    {
        "role": "system",
        "content": "You are a stegosaurus, but don't be too obvious about it."
    },
    {
        "role": "user",
        "content": "What's good to eat around here?"
    }
])
weave.publish(prompt, name="dino_prompt")

from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
  model="gpt-4o",
  # highlight-next-line
  messages=prompt.format(),
)
```

## Parameterizing prompts

As the `format` method's name suggests, you can pass arguments to
fill in template placeholders in the content string.

```python
import weave
weave.init('intro-example')

# highlight-next-line
prompt = weave.StringPrompt("Solve the equation {equation}")
weave.publish(prompt, name="calculator_prompt")

from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
  model="gpt-4o",
  messages=[
    {
      "role": "user",
      # highlight-next-line
      "content": prompt.format(equation="1 + 1 = ?")
    }
  ],
)
```

This also works with `MessagesPrompt`.

```python
import weave
weave.init('intro-example')

# highlight-next-line
prompt = weave.MessagesPrompt([
{
    "role": "system",
    "content": "You will be provided with a description of a scene and your task is to provide a single word that best describes an associated emotion."
},
{
    "role": "user",
    "content": "{scene}"
}
])
weave.publish(prompt, name="emotion_prompt")

from openai import OpenAI
client = OpenAI()

response = client.chat.completions.create(
  model="gpt-4o",
  # highlight-next-line
  messages=prompt.format(scene="A dog is lying on a dock next to a fisherman."),
)
```</doc><doc title="scorers">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Evaluation Metrics

## Evaluations in Weave

In Weave, Scorers are used to evaluate AI outputs and return evaluation metrics. They take the AI's output, analyze it, and return a dictionary of results. Scorers can use your input data as reference if needed and can also output extra information, such as explanations or reasonings from the evaluation.

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    Scorers are passed to a `weave.Evaluation` object during evaluation. There are two types of Scorers in weave:

    1. **Function-based Scorers:** Simple Python functions decorated with `@weave.op`.
    2. **Class-based Scorers:** Python classes that inherit from `weave.Scorer` for more complex evaluations.

    Scorers must return a dictionary and can return multiple metrics, nested metrics and non-numeric values such as text returned from a LLM-evaluator about its reasoning.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    Scorers are special ops passed to a `weave.Evaluation` object during evaluation.
  </TabItem>
</Tabs>

## Create your own Scorers

### Function-based Scorers

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    These are functions decorated with `@weave.op` that return a dictionary. They're great for simple evaluations like:

    ```python
    import weave

    @weave.op
    def evaluate_uppercase(text: str) -> dict:
        return {"text_is_uppercase": text.isupper()}

    my_eval = weave.Evaluation(
        dataset=[{"text": "HELLO WORLD"}],
        scorers=[evaluate_uppercase]
    )
    ```

    When the evaluation is run, `evaluate_uppercase` checks if the text is all uppercase.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    These are functions wrapped with `weave.op` that accept an object with `modelOutput` and optionally `datasetRow`.  They're great for simple evaluations like:
    ```typescript
    import * as weave from 'weave'

    const evaluateUppercase = weave.op(
        ({modelOutput}) => modelOutput.toUpperCase() === modelOutput,
        {name: 'textIsUppercase'}
    );


    const myEval = new weave.Evaluation({
        dataset: [{text: 'HELLO WORLD'}],
        scorers: [evaluateUppercase],
    })
    ```

  </TabItem>
</Tabs>

### Class-based Scorers

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    For more advanced evaluations, especially when you need to keep track of additional scorer metadata, try different prompts for your LLM-evaluators, or make multiple function calls, you can use the `Scorer` class.

    **Requirements:**

    1. Inherit from `weave.Scorer`.
    2. Define a `score` method decorated with `@weave.op`.
    3. The `score` method must return a dictionary.

    Example:

    ```python
    import weave
    from openai import OpenAI
    from weave import Scorer

    llm_client = OpenAI()

    #highlight-next-line
    class SummarizationScorer(Scorer):
        model_id: str = "gpt-4o"
        system_prompt: str = "Evaluate whether the summary is good."

        @weave.op
        def some_complicated_preprocessing(self, text: str) -> str:
            processed_text = "Original text: \n" + text + "\n"
            return processed_text

        @weave.op
        def call_llm(self, summary: str, processed_text: str) -> dict:
            res = llm_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": (
                        f"Analyse how good the summary is compared to the original text."
                        f"Summary: {summary}\n{processed_text}"
                    )}])
            return {"summary_quality": res}

        @weave.op
        def score(self, output: str, text: str) -> dict:
            """Score the summary quality.

            Args:
                output: The summary generated by an AI system
                text: The original text being summarized
            """
            processed_text = self.some_complicated_preprocessing(text)
            eval_result = self.call_llm(summary=output, processed_text=processed_text)
            return {"summary_quality": eval_result}

    evaluation = weave.Evaluation(
        dataset=[{"text": "The quick brown fox jumps over the lazy dog."}],
        scorers=[summarization_scorer])
    ```

    This class evaluates how good a summary is by comparing it to the original text.

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

## How Scorers Work

### Scorer Keyword Arguments

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    Scorers can access both the output from your AI system and the input data from the dataset row.

    - **Input:** If you would like your scorer to use data from your dataset row, such as a "label" or "target" column then you can easily make this available to the scorer by adding a `label` or `target` keyword argument to your scorer definition.

    For example if you wanted to use a column called "label" from your dataset then your scorer function (or `score` class method) would have a parameter list like this:

    ```python
    @weave.op
    def my_custom_scorer(output: str, label: int) -> dict:
        ...
    ```

    When a weave `Evaluation` is run, the output of the AI system is passed to the `output` parameter. The `Evaluation` also automatically tries to match any additional scorer argument names to your dataset columns. If customizing your scorer arguments or dataset columns is not feasible, you can use column mapping - see below for more.

    - **Output:** Include an `output` parameter in your scorer function's signature to access the AI system's output.

    ### Mapping Column Names with `column_map`

    Sometimes, the `score` methods' argument names don't match the column names in your dataset. You can fix this using a `column_map`.

    If you're using a class-based scorer, pass a dictionary to the `column_map` attribute of `Scorer` when you initialise your scorer class. This dictionary maps your `score` method's argument names to the dataset's column names, in the order: `{scorer_keyword_argument: dataset_column_name}`.

    Example:

    ```python
    import weave
    from weave import Scorer

    # A dataset with news articles to be summarised
    dataset = [
        {"news_article": "The news today was great...", "date": "2030-04-20", "source": "Bright Sky Network"},
        ...
    ]

    # Scorer class
    class SummarizationScorer(Scorer):

        @weave.op
        def score(output, text) -> dict:
            """
                output: output summary from a LLM summarization system
                text: the text being summarised
            """
            ...  # evaluate the quality of the summary

    # create a scorer with a column mapping the `text` argument to the `news_article` data column
    scorer = SummarizationScorer(column_map={"text" : "news_article"})
    ```

    Now, the `text` argument in the `score` method will receive data from the `news_article` dataset column.

    **Notes:**

    - Another equivalent option to map your columns is to subclass the `Scorer` and overload the `score` method mapping the columns explicitly.

    ```python
    import weave
    from weave import Scorer

    class MySummarizationScorer(SummarizationScorer):

        @weave.op
        def score(self, output: str, news_article: str) -> dict:  # Added type hints
            # overload the score method and map columns manually
            return super().score(output=output, text=news_article)
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    Scorers can access both the output from your AI system and the contents of the dataset row.

    You can easily access relevant columns from the dataset row by adding a `datasetRow` keyword argument to your scorer definition.

    ```typescript
    const myScorer = weave.op(
        ({modelOutput, datasetRow}) => {
            return modelOutput * 2 === datasetRow.expectedOutputTimesTwo;
        },
        {name: 'myScorer'}
    );
    ```

    ### Mapping Column Names with `columnMapping`
    :::warning

    In TypeScript, this feature is currently on the `Evaluation` object, not individual scorers!

    :::

    Sometimes your `datasetRow` keys will not exactly match the scorer's naming scheme, but they are semantically similar. You can map the columns using the `Evaluation`'s `columnMapping` option.

    The mapping is always from the scorer's perspective, i.e. `{scorer_key: dataset_column_name}`.

    Example:

    ```typescript
    const myScorer = weave.op(
        ({modelOutput, datasetRow}) => {
            return modelOutput * 2 === datasetRow.expectedOutputTimesTwo;
        },
        {name: 'myScorer'}
    );

    const myEval = new weave.Evaluation({
        dataset: [{expected: 2}],
        scorers: [myScorer],
        columnMapping: {expectedOutputTimesTwo: 'expected'}
    });
    ```

  </TabItem>
</Tabs>

### Final summarization of the scorer

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    During evaluation, the scorer will be computed for each row of your dataset. To provide a final score for the evaluation we provide an `auto_summarize` depending on the returning type of the output.
    - Averages are computed for numerical columns
    - Count and fraction for boolean columns
    - Other column types are ignored

    You can override the `summarize` method on the `Scorer` class and provide your own way of computing the final scores. The `summarize` function expects:

    - A single parameter `score_rows`: This is a list of dictionaries, where each dictionary contains the scores returned by the `score` method for a single row of your dataset.
    - It should return a dictionary containing the summarized scores.

    **Why this is useful?**

    When you need to score all rows before deciding on the final value of the score for the dataset.

    ```python
    class MyBinaryScorer(Scorer):
        """
        Returns True if the full output matches the target, False if not
        """

        @weave.op
        def score(output, target):
            return {"match": if output == target}

        def summarize(self, score_rows: list) -> dict:
            full_match = all(row["match"] for row in score_rows)
            return {"full_match": full_match}
    ```

    > In this example, the default `auto_summarize` would have returned the count and proportion of True.

    If you want to learn more, check the implementation of [CorrectnessLLMJudge](/tutorial-rag#optional-defining-a-scorer-class).

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    During evaluation, the scorer will be computed for each row of your dataset.  To provide a final score, we use an internal `summarizeResults` function that aggregates depending on the output type.
    - Averages are computed for numerical columns
    - Count and fraction for boolean columns
    - Other column types are ignored

    We don't currently support custom summarization.

  </TabItem>
</Tabs>

## Predefined Scorers

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    **Installation**

    To use Weave's predefined scorers you need to install some additional dependencies:

    ```bash
    pip install weave[scorers]
    ```

    **LLM-evaluators**

    The pre-defined scorers that use LLMs support the OpenAI, Anthropic, Google GenerativeAI and MistralAI clients. They also use `weave`'s `InstructorLLMScorer` class, so you'll need to install the [`instructor`](https://github.com/instructor-ai/instructor) Python package to be able to use them. You can get all necessary dependencies with `pip install "weave[scorers]"`

    ### `HallucinationFreeScorer`

    This scorer checks if your AI system's output includes any hallucinations based on the input data.

    ```python
    from weave.scorers import HallucinationFreeScorer

    llm_client = ... # initialize your LLM client here

    scorer = HallucinationFreeScorer(
        client=llm_client,
        model_id="gpt-4o"
    )
    ```

    **Customization:**

    - Customize the `system_prompt` and `user_prompt` attributes of the scorer to define what "hallucination" means for you.

    **Notes:**

    - The `score` method expects an input column named `context`. If your dataset uses a different name, use the `column_map` attribute to map `context` to the dataset column.

    Here you have an example in the context of an evaluation:

    ```python
    import asyncio
    from openai import OpenAI
    import weave
    from weave.scorers import HallucinationFreeScorer

    # Initialize clients and scorers
    llm_client = OpenAI()
    hallucination_scorer = HallucinationFreeScorer(
        client=llm_client,
        model_id="gpt-4o",
        column_map={"context": "input", "output": "other_col"}
    )

    # Create dataset
    dataset = [
        {"input": "John likes various types of cheese."},
        {"input": "Pepe likes various types of cheese."},
    ]

    @weave.op
    def model(input: str) -> str:
        return "The person's favorite cheese is cheddar."

    # Run evaluation
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[hallucination_scorer],
    )
    result = asyncio.run(evaluation.evaluate(model))
    print(result)
    # {'HallucinationFreeScorer': {'has_hallucination': {'true_count': 2, 'true_fraction': 1.0}}, 'model_latency': {'mean': 1.4395725727081299}}
    ```

    ---

    ### `SummarizationScorer`

    Use an LLM to compare a summary to the original text and evaluate the quality of the summary.

    ```python
    from weave.scorers import SummarizationScorer

    llm_client = ... # initialize your LLM client here

    scorer = SummarizationScorer(
        client=llm_client,
        model_id="gpt-4o"
    )
    ```

    **How It Works:**

    This scorer evaluates summaries in two ways:

    1. **Entity Density:** Checks the ratio of unique entities (like names, places, or things) mentioned in the summary to the total word count in the summary in order to estimate the "information density" of the summary. Uses an LLM to extract the entities. Similar to how entity density is used in the Chain of Density paper, https://arxiv.org/abs/2309.04269

    2. **Quality Grading:** Uses an LLM-evaluator to grade the summary as `poor`, `ok`, or `excellent`. These grades are converted to scores (0.0 for poor, 0.5 for ok, and 1.0 for excellent) so you can calculate averages.

    **Customization:**

    - Adjust `summarization_evaluation_system_prompt` and `summarization_evaluation_prompt` to define what makes a good summary.

    **Notes:**

    - This scorer uses the `InstructorLLMScorer` class.
    - The `score` method expects the original text that was summarized to be present in the `input` column of the dataset. Use the `column_map` class attribute to map `input` to the correct dataset column if needed.

    Here you have an example usage of the `SummarizationScorer` in the context of an evaluation:

    ```python
    import asyncio
    from openai import OpenAI
    import weave
    from weave.scorers import SummarizationScorer

    class SummarizationModel(weave.Model):
        @weave.op()
        async def predict(self, input: str) -> str:
            return "This is a summary of the input text."

    # Initialize clients and scorers
    llm_client = OpenAI()
    model = SummarizationModel()
    summarization_scorer = SummarizationScorer(
        client=llm_client,
        model_id="gpt-4o",
    )
    # Create dataset
    dataset = [
        {"input": "The quick brown fox jumps over the lazy dog."},
        {"input": "Artificial Intelligence is revolutionizing various industries."}
    ]

    # Run evaluation
    evaluation = weave.Evaluation(dataset=dataset, scorers=[summarization_scorer])
    results = asyncio.run(evaluation.evaluate(model))
    print(results)
    # {'SummarizationScorer': {'is_entity_dense': {'true_count': 0, 'true_fraction': 0.0}, 'summarization_eval_score': {'mean': 0.0}, 'entity_density': {'mean': 0.0}}, 'model_latency': {'mean': 6.210803985595703e-05}}
    ```

    ---

    ### `OpenAIModerationScorer`

    The `OpenAIModerationScorer` uses OpenAI's Moderation API to check if the AI system's output contains disallowed content, such as hate speech or explicit material.

    ```python
    from weave.scorers import OpenAIModerationScorer
    from openai import OpenAI

    oai_client = OpenAI(api_key=...) # initialize your LLM client here

    scorer = OpenAIModerationScorer(
        client=oai_client,
        model_id="text-embedding-3-small"
    )
    ```

    **How It Works:**

    - Sends the AI's output to the OpenAI Moderation endpoint and returns a dictionary indicating whether the content is flagged and details about the categories involved.

    **Notes:**

    - Requires the `openai` Python package.
    - The client must be an instance of OpenAI's `OpenAI` or `AsyncOpenAI` client.

    Here you have an example in the context of an evaluation:

    ```python
    import asyncio
    from openai import OpenAI
    import weave
    from weave.scorers import OpenAIModerationScorer

    class MyModel(weave.Model):
        @weave.op
        async def predict(self, input: str) -> str:
            return input

    # Initialize clients and scorers
    client = OpenAI()
    model = MyModel()
    moderation_scorer = OpenAIModerationScorer(client=client)

    # Create dataset
    dataset = [
        {"input": "I love puppies and kittens!"},
        {"input": "I hate everyone and want to hurt them."}
    ]

    # Run evaluation
    evaluation = weave.Evaluation(dataset=dataset, scorers=[moderation_scorer])
    results = asyncio.run(evaluation.evaluate(model))
    print(results)
    # {'OpenAIModerationScorer': {'flagged': {'true_count': 1, 'true_fraction': 0.5}, 'categories': {'violence': {'true_count': 1, 'true_fraction': 1.0}}}, 'model_latency': {'mean': 9.500980377197266e-05}}
    ```

    ---

    ### `EmbeddingSimilarityScorer`

    The `EmbeddingSimilarityScorer` computes the cosine similarity between the embeddings of the AI system's output and a target text from your dataset. It's useful for measuring how similar the AI's output is to a reference text.

    ```python
    from weave.scorers import EmbeddingSimilarityScorer

    llm_client = ...  # initialise your LlM client

    similarity_scorer = EmbeddingSimilarityScorer(
        client=llm_client
        target_column="reference_text",  # the dataset column to compare the output against
        threshold=0.4  # the cosine similarity threshold to use
    )
    ```

    **Parameters:**

    - `target`: This scorer expects a `target` column in your dataset, it will calculate the cosine similarity of the embeddings of the `target` column to the AI system output. If your dataset doesn't contain a column called `target` you can use the scorers `column_map` attribute to map `target` to the appropriate column name in your dataset. See the Column Mapping section for more.
    - `threshold` (float): The minimum cosine similarity score between the embedding of the AI system output and the embdedding of the `target`, above which the 2 samples are considered "similar", (defaults to `0.5`). `threshold` can be in a range from -1 to 1:
    - 1 indicates identical direction.
    - 0 indicates orthogonal vectors.
    - -1 indicates opposite direction.

    The correct cosine similarity threshold to set can fluctuate quite a lot depending on your use case, we advise exploring different thresholds.

    Here you have an example usage of the `EmbeddingSimilarityScorer` in the context of an evaluation:

    ```python
    import asyncio
    from openai import OpenAI
    import weave
    from weave.scorers import EmbeddingSimilarityScorer

    # Initialize clients and scorers
    client = OpenAI()
    similarity_scorer = EmbeddingSimilarityScorer(
        client=client,
        threshold=0.7,
        column_map={"target": "reference"}
    )

    # Create dataset
    dataset = [
        {
            "input": "He's name is John",
            "reference": "John likes various types of cheese.",
        },
        {
            "input": "He's name is Pepe.",
            "reference": "Pepe likes various types of cheese.",
        },
    ]

    # Define model
    @weave.op
    def model(input: str) -> str:
        return "John likes various types of cheese."

    # Run evaluation
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[similarity_scorer],
    )
    result = asyncio.run(evaluation.evaluate(model))
    print(result)
    # {'EmbeddingSimilarityScorer': {'is_similar': {'true_count': 1, 'true_fraction': 0.5}, 'similarity_score': {'mean': 0.8448514031462045}}, 'model_latency': {'mean': 0.45862746238708496}}
    ```

    ---

    ### `ValidJSONScorer`

    The ValidJSONScorer checks whether the AI system's output is valid JSON. This scorer is useful when you expect the output to be in JSON format and need to verify its validity.

    ```python
    from weave.scorers import ValidJSONScorer

    json_scorer = ValidJSONScorer()
    ```

    Here you have an example usage of the `ValidJSONScorer` in the context of an evaluation:

    ```python
    import asyncio
    import weave
    from weave.scorers import ValidJSONScorer

    class JSONModel(weave.Model):
        @weave.op()
        async def predict(self, input: str) -> str:
            # This is a placeholder.
            # In a real scenario, this would generate JSON.
            return '{"key": "value"}'

    model = JSONModel()
    json_scorer = ValidJSONScorer()

    dataset = [
        {"input": "Generate a JSON object with a key and value"},
        {"input": "Create an invalid JSON"}
    ]

    evaluation = weave.Evaluation(dataset=dataset, scorers=[json_scorer])
    results = asyncio.run(evaluation.evaluate(model))
    print(results)
    # {'ValidJSONScorer': {'json_valid': {'true_count': 2, 'true_fraction': 1.0}}, 'model_latency': {'mean': 8.58306884765625e-05}}
    ```

    ---

    ### `ValidXMLScorer`

    The `ValidXMLScorer` checks whether the AI system's output is valid XML. This is useful when expecting XML-formatted outputs.

    ```python
    from weave.scorers import ValidXMLScorer

    xml_scorer = ValidXMLScorer()
    ```

    Here you have an example usage of the `ValidXMLScorer` in the context of an evaluation:

    ```python
    import asyncio
    import weave
    from weave.scorers import ValidXMLScorer

    class XMLModel(weave.Model):
        @weave.op()
        async def predict(self, input: str) -> str:
            # This is a placeholder. In a real scenario, this would generate XML.
            return '<root><element>value</element></root>'

    model = XMLModel()
    xml_scorer = ValidXMLScorer()

    dataset = [
        {"input": "Generate a valid XML with a root element"},
        {"input": "Create an invalid XML"}
    ]

    evaluation = weave.Evaluation(dataset=dataset, scorers=[xml_scorer])
    results = asyncio.run(evaluation.evaluate(model))
    print(results)
    # {'ValidXMLScorer': {'xml_valid': {'true_count': 2, 'true_fraction': 1.0}}, 'model_latency': {'mean': 8.20159912109375e-05}}
    ```

    ---

    ### `PydanticScorer`

    The `PydanticScorer` validates the AI system's output against a Pydantic model to ensure it adheres to a specified schema or data structure.

    ```python
    from weave.scorers import PydanticScorer
    from pydantic import BaseModel

    class FinancialReport(BaseModel):
        revenue: int
        year: str

    pydantic_scorer = PydanticScorer(model=FinancialReport)
    ```

    ---

    ### RAGAS - `ContextEntityRecallScorer`

    The `ContextEntityRecallScorer` estimates context recall by extracting entities from both the AI system's output and the provided context, then computing the recall score. Based on the [RAGAS](https://github.com/explodinggradients/ragas) evaluation library

    ```python
    from weave.scorers import ContextEntityRecallScorer

    llm_client = ...  # initialise your LlM client

    entity_recall_scorer = ContextEntityRecallScorer(
        client=llm_client
        model_id="your-model-id"
    )
    ```

    **How It Works:**

    - Uses an LLM to extract unique entities from the output and context and calculates recall.
    - **Recall** indicates the proportion of important entities from the context that are captured in the output, helping to assess the model's effectiveness in retrieving relevant information.
    - Returns a dictionary with the recall score.

    **Notes:**

    - Expects a `context` column in your dataset, use `column_map` to map `context` to another dataset column if needed.

    ---

    ### RAGAS - `ContextRelevancyScorer`

    The `ContextRelevancyScorer` evaluates the relevancy of the provided context to the AI system's output. It helps determine if the context used is appropriate for generating the output. Based on the [RAGAS](https://github.com/explodinggradients/ragas) evaluation library.

    ```python
    from weave.scorers import ContextRelevancyScorer

    llm_client = ...  # initialise your LlM client

    relevancy_scorer = ContextRelevancyScorer(
        llm_client = ...  # initialise your LlM client
        model_id="your-model-id"
        )
    ```

    **How It Works:**

    - Uses an LLM to rate the relevancy of the context to the output on a scale from 0 to 1.
    - Returns a dictionary with the `relevancy_score`.

    **Notes:**

    - Expects a `context` column in your dataset, use `column_map` to map `context` to another dataset column if needed.
    - Customize the `relevancy_prompt` to define how relevancy is assessed.

    Here you have an example usage of `ContextEntityRecallScorer` and `ContextRelevancyScorer` in the context of an evaluation:

    ```python
    import asyncio
    from textwrap import dedent
    from openai import OpenAI
    import weave
    from weave.scorers import ContextEntityRecallScorer, ContextRelevancyScorer

    class RAGModel(weave.Model):
        @weave.op()
        async def predict(self, question: str) -> str:
            "Retrieve relevant context"
            return "Paris is the capital of France."


    model = RAGModel()

    # Define prompts
    relevancy_prompt: str = dedent("""
        Given the following question and context, rate the relevancy of the context to the question on a scale from 0 to 1.

        Question: {question}
        Context: {context}
        Relevancy Score (0-1):
        """)

    # Initialize clients and scorers
    llm_client = OpenAI()
    entity_recall_scorer = ContextEntityRecallScorer(
        client=client,
        model_id="gpt-4o",
    )

    relevancy_scorer = ContextRelevancyScorer(
        client=llm_client,
        model_id="gpt-4o",
        relevancy_prompt=relevancy_prompt
    )

    # Create dataset
    dataset = [
        {
            "question": "What is the capital of France?",
            "context": "Paris is the capital city of France."
        },
        {
            "question": "Who wrote Romeo and Juliet?",
            "context": "William Shakespeare wrote many famous plays."
        }
    ]

    # Run evaluation
    evaluation = weave.Evaluation(
        dataset=dataset,
        scorers=[entity_recall_scorer, relevancy_scorer]
    )
    results = asyncio.run(evaluation.evaluate(model))
    print(results)
    # {'ContextEntityRecallScorer': {'recall': {'mean': 0.3333333333333333}}, 'ContextRelevancyScorer': {'relevancy_score': {'mean': 0.5}}, 'model_latency': {'mean': 9.393692016601562e-05}}
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs></doc><doc title="serve"># Serve

Given a Weave ref to any Weave Model you can run:

```
weave serve <ref>
```

to run a FastAPI server for that model. Visit [http://0.0.0.0:9996/docs](http://0.0.0.0:9996/docs) to query the model interactively.

## Install FastAPI

```bash
pip install fastapi uvicorn
```

## Serve Model

In a terminal, call:

```bash
weave serve <your model ref>
```

Get your model ref by navigating to the model and copying it from the UI. It should look like:
`weave:///your_entity/project-name/YourModel:<hash>`

To use it, navigate to the Swagger UI link, click the predict endpoint and then click "Try it out!".</doc><doc title="tools"># Tools & Utilities

Weave is developing a set of tools and utilities to help with your workflow and deployment process for AI applications. These are currently in early alpha stages and subject to change. Here's an overview of what we're working on:

## Serve (experimental)

[Serve](/guides/tools/serve) is a feature to expose your Weave ops and models as API endpoints. We're exploring possibilities such as:

- Creating web services for your Weave components
- Integrating Weave components into existing applications
- Providing a way to test models in a more production-like setting

## Deploy (experimental)

[Deploy](/guides/tools/deploy) is another alpha-stage utility we're developing to help with deploying Weave ops and models. Some potential features we're considering include:

- Pushing models to cloud platforms
- Managing different deployment environments
- Exploring ways to automate parts of the deployment process

Please note that these tools are still in very early stages of development. They may not be fully functional, could change significantly, or might be discontinued. We recommend using them for experimental purposes only at this time.</doc><doc title="tracing">import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import { DesktopWindow } from '../../../src/components/DesktopImage'
import TracingCallsMacroImage from '@site/static/img/screenshots/calls_macro.png';
import TracingCallsFilterImage from '@site/static/img/screenshots/calls_filter.png';
import BasicCallImage from '@site/static/img/screenshots/basic_call.png';

# Calls

<DesktopWindow 
  images={[
    TracingCallsMacroImage,
    BasicCallImage,
    TracingCallsFilterImage,
  ]}
  alt="Screenshot of Weave Calls"
  title="Weave Calls"
/>

:::info[Calls]
Calls are the fundamental building block in Weave. They represent a single execution of a function, including:
- Inputs (arguments)
- Outputs (return value) 
- Metadata (duration, exceptions, LLM usage, etc.)

Calls are similar to spans in the [OpenTelemetry](https://opentelemetry.io) data model. A Call can:
- Belong to a Trace (a collection of calls in the same execution context)
- Have parent and child Calls, forming a tree structure
:::

## Creating Calls

There are three main ways to create Calls in Weave:

### 1. Automatic Tracking of LLM Libraries


<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    Weave automatically tracks [calls to common LLM libraries](../integrations/index.md) like `openai`, `anthropic`, `cohere`, and `mistral`. Simply call [`weave.init('project_name')`](../../reference/python-sdk/weave/index.md#function-init) at the start of your program:

    ```python showLineNumbers
    import weave

    from openai import OpenAI
    client = OpenAI()

    # Initialize Weave Tracing
    weave.init('intro-example')

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "user",
                "content": "How are you?"
            }
        ],
        temperature=0.8,
        max_tokens=64,
        top_p=1,
    )
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    Weave automatically tracks [calls to common LLM libraries](../integrations/index.md) like `openai`. Simply call [`await weave.init('project_name')`](../../reference/typescript-sdk/weave/functions/init.md) and wrap your OpenAI client with [`weave.wrapOpenAI`](../../reference/typescript-sdk/weave/functions/wrapOpenAI.md) at the start of your program:

    ```typescript showLineNumbers
    import OpenAI from 'openai'
    import * as weave from 'weave'

    const client = weave.wrapOpenAI(new OpenAI())

    // Initialize Weave Tracing
    await weave.init('intro-example')

    const response = await client.chat.completions.create({
      model: 'gpt-4',
      messages: [
        {
          role: 'user',
          content: 'How are you?',
        },
      ],
      temperature: 0.8,
      max_tokens: 64,
      top_p: 1,
    });
    ```

  </TabItem>
</Tabs>



### 2. Decorating/Wrapping Functions

However, often LLM applications have additional logic (such as pre/post processing, prompts, etc.) that you want to track.

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    Weave allows you to manually track these calls using the [`@weave.op`](../../reference/python-sdk/weave/index.md#function-op) decorator. For example:

    ```python showLineNumbers
    import weave

    # Initialize Weave Tracing
    weave.init('intro-example')

    # Decorate your function
    @weave.op
    def my_function(name: str):
        return f"Hello, {name}!"

    # Call your function -- Weave will automatically track inputs and outputs
    print(my_function("World"))
    ```

    This works for both functions as well as methods on classes:


    ```python showLineNumbers
    import weave

    # Initialize Weave Tracing
    weave.init("intro-example")

    class MyClass:
        # Decorate your method
        @weave.op
        def my_method(self, name: str):
            return f"Hello, {name}!"

    instance = MyClass()

    # Call your method -- Weave will automatically track inputs and outputs
    print(instance.my_method("World"))
    ```
  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    Weave allows you to manually track these calls by wrapping your function with [`weave.op`](../../reference/typescript-sdk/weave/functions/op.md). For example:

    ```typescript showLineNumbers
    import * as weave from 'weave'

    await weave.init('intro-example')

    function myFunction(name: string) {
        return `Hello, ${name}!`
    }

    const myFunctionOp = weave.op(myFunction)
    ```

    You can also define the wrapping inline:

    ```typescript
    const myFunctionOp = weave.op((name: string) => `Hello, ${name}!`)
    ```

    This works for both functions as well as methods on classes:

    ```typescript
    class MyClass {
        constructor() {
            this.myMethod = weave.op(this.myMethod)
        }

        myMethod(name: string) {
            return `Hello, ${name}!`
        }
    }
    ```
  </TabItem>
</Tabs>


#### Getting a handle to the Call object during execution

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    Sometimes it is useful to get a handle to the `Call` object itself. You can do this by calling the `op.call` method, which returns both the result and the `Call` object. For example:

    ```python showLineNumbers
    result, call = my_function.call("World")
    ```

    Then, `call` can be used to set / update / fetch additional properties (most commonly used to get the ID of the call to be used for feedback).

    :::note
    If your op is a method on a class, you need to pass the instance as the first argument to the op (see example below).
    :::

    ```python showLineNumbers
    # Notice that we pass the `instance` as the first argument.
    # highlight-next-line
    print(instance.my_method.call(instance, "World"))
    ```


    ```python showLineNumbers
    import weave

    # Initialize Weave Tracing
    weave.init("intro-example")

    class MyClass:
        # Decorate your method
        @weave.op
        def my_method(self, name: str):
            return f"Hello, {name}!"

    instance = MyClass()

    # Call your method -- Weave will automatically track inputs and outputs
    instance.my_method.call(instance, "World")
    ```
  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>



#### Call Display Name

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    Sometimes you may want to override the display name of a call. You can achieve this in one of four ways:

    1. Change the display name at the time of calling the op:

    ```python showLineNumbers
    result = my_function("World", __weave={"display_name": "My Custom Display Name"})
    ```

    :::note

    Using the `__weave` dictionary sets the call display name which will take precedence over the Op display name.

    :::

    2. Change the display name on a per-call basis. This uses the [`Op.call`](../../reference/python-sdk/weave/trace/weave.trace.op.md#function-call) method to return a `Call` object, which you can then use to set the display name using [`Call.set_display_name`](../../reference/python-sdk/weave/trace/weave.trace.weave_client.md#method-set_display_name).
    ```python showLineNumbers
    result, call = my_function.call("World")
    call.set_display_name("My Custom Display Name")
    ```

    3. Change the display name for all Calls of a given Op:

    ```python showLineNumbers
    @weave.op(call_display_name="My Custom Display Name")
    def my_function(name: str):
        return f"Hello, {name}!"
    ```

    4. The `call_display_name` can also be a function that takes in a `Call` object and returns a string.  The `Call` object will be passed automatically when the function is called, so you can use it to dynamically generate names based on the function's name, call inputs, attributes, etc.

    1. One common use case is just appending a timestamp to the function's name.

        ```py
        from datetime import datetime

        @weave.op(call_display_name=lambda call: f"{call.func_name}__{datetime.now()}")
        def func():
            return ...
        ```

    2. You can also get creative with custom attributes

        ```py
        def custom_attribute_name(call):
            model = call.attributes["model"]
            revision = call.attributes["revision"]
            now = call.attributes["date"]

            return f"{model}__{revision}__{now}"

        @weave.op(call_display_name=custom_attribute_name)
        def func():
            return ...

        with weave.attributes(
            {
                "model": "finetuned-llama-3.1-8b",
                "revision": "v0.1.2",
                "date": "2024-08-01",
            }
        ):
            func()  # the display name will be "finetuned-llama-3.1-8b__v0.1.2__2024-08-01"


            with weave.attributes(
                {
                    "model": "finetuned-gpt-4o",
                    "revision": "v0.1.3",
                    "date": "2024-08-02",
                }
            ):
                func()  # the display name will be "finetuned-gpt-4o__v0.1.3__2024-08-02"
        ```


    **Technical Note:** "Calls" are produced by "Ops". An Op is a function or method that is decorated with `@weave.op`. 
    By default, the Op's name is the function name, and the associated calls will have the same display name. The above example shows how to override the display name for all Calls of a given Op.  Sometimes, users wish to override the name of the Op itself. This can be achieved in one of two ways:

    1. Set the `name` property of the Op before any calls are logged
    ```python showLineNumbers
    my_function.name = "My Custom Op Name"
    ```

    2. Set the `name` option on the op decorator
    ```python showLineNumbers
    @weave.op(name="My Custom Op Name)
    ```
  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>





#### Attributes

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>
    When calling tracked functions, you can add additional metadata to the call by using the [`weave.attributes`](../../reference/python-sdk/weave/index.md#function-attributes) context manager. In the example below, we add an `env` attribute to the call specified as `'production'`.

    ```python showLineNumbers
    # ... continued from above ...

    # Add additional "attributes" to the call
    with weave.attributes({'env': 'production'}):
        print(my_function.call("World"))
    ```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>

### 3. Manual Call Tracking

You can also manually create Calls using the API directly.

<Tabs groupId="programming-language">
    <TabItem value="python" label="Python" default>

        ```python showLineNumbers
        import weave

        # Initialize Weave Tracing
        weave.init('intro-example')

        def my_function(name: str):
            # Start a call
            call = weave.create_call(op="my_function", inputs={"name": name})

            # ... your function code ...

            # End a call
            weave.finish_call(call, output="Hello, World!")

        # Call your function
        print(my_function("World"))
        ```

    </TabItem>
    <TabItem value="typescript" label="TypeScript">

    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```

    </TabItem>

    <TabItem value="service_api" label="HTTP API">
    * Start a call: [POST `/call/start`](../../reference/service-api/call-start-call-start-post.api.mdx)
    * End a call: [POST `/call/end`](../../reference/service-api/call-end-call-end-post.api.mdx)
    ```bash
    curl -L 'https://trace.wandb.ai/call/start' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json' \
    -d '{
        "start": {
            "project_id": "string",
            "id": "string",
            "op_name": "string",
            "display_name": "string",
            "trace_id": "string",
            "parent_id": "string",
            "started_at": "2024-09-08T20:07:34.849Z",
            "attributes": {},
            "inputs": {},
            "wb_run_id": "string"
        }
    }
    ```
    </TabItem>
</Tabs>




## Viewing Calls
<Tabs groupId="programming-language">
    <TabItem value="web_app" label="Web App">
    To view a call in the web app:
    1. Navigate to your project's "Traces" tab
    2. Find the call you want to view in the list
    3. Click on the call to open its details page
    
    The details page will show the call's inputs, outputs, runtime, and any additional attributes or metadata.
    
    ![View Call in Web App](../../../static/img/screenshots/basic_call.png)
    </TabItem>
    <TabItem value="python_sdk" label="Python">
    To view a call using the Python API, you can use the [`get_call`](../../reference/python-sdk/weave/trace/weave.trace.weave_client#method-get_call) method:

    ```python
    import weave

    # Initialize the client
    client = weave.init("your-project-name")

    # Get a specific call by its ID
    call = client.get_call("call-uuid-here")

    print(call)
    ```

    </TabItem>
    <TabItem value="typescript" label="TypeScript">
    ```typescript showLineNumbers
    import * as weave from 'weave'

    // Initialize the client
    const client = await weave.init('intro-example')

    // Get a specific call by its ID
    const call = await client.getCall('call-uuid-here')

    console.log(call)
    ```
    </TabItem>

    <TabItem value="service_api" label="HTTP API">
    To view a call using the Service API, you can make a request to the [`/call/read`](../../reference/service-api/call-read-call-read-post.api.mdx) endpoint.

    ```bash
    curl -L 'https://trace.wandb.ai/call/read' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json' \
    -d '{
        "project_id": "string",
        "id": "string",
    }'
    ```
    </TabItem>
</Tabs>


## Updating Calls

Calls are mostly immutable once created, however, there are a few mutations which are supported:
* [Set Display Name](#set-display-name)
* [Add Feedback](#add-feedback)
* [Delete a Call](#delete-a-call)

All of these mutations can be performed from the UI by navigating to the call detail page:

![Update Call in Web App](../../../static/img/call_edit_screenshot.png)

### Set Display Name

<Tabs groupId="client-layer">
    <TabItem value="python_sdk" label="Python">
    In order to set the display name of a call, you can use the [`Call.set_display_name`](../../reference/python-sdk/weave/trace/weave.trace.weave_client.md#method-set_display_name) method.

    ```python showLineNumbers
    import weave

    # Initialize the client
    client = weave.init("your-project-name")

    # Get a specific call by its ID
    call = client.get_call("call-uuid-here")

    # Set the display name of the call
    call.set_display_name("My Custom Display Name")
    ```
    </TabItem>
    <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
    </TabItem>
    <TabItem value="service_api" label="HTTP API">
    To set the display name of a call using the Service API, you can make a request to the [`/call/update`](../../reference/service-api/call-update-call-update-post.api.mdx) endpoint.

    ```bash
    curl -L 'https://trace.wandb.ai/call/update' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json' \
    -d '{
        "project_id": "string",
        "call_id": "string",
        "display_name": "string",
    }'
    ```
    </TabItem>
</Tabs>

### Add Feedback 

Please see the [Feedback Documentation](./feedback.md) for more details.

### Delete a Call

<Tabs groupId="client-layer">
    <TabItem value="python_sdk" label="Python">
    To delete a call using the Python API, you can use the [`Call.delete`](../../reference/python-sdk/weave/trace/weave.trace.weave_client.md#method-delete) method.

    ```python showLineNumbers
    import weave

    # Initialize the client
    client = weave.init("your-project-name")

    # Get a specific call by its ID
    call = client.get_call("call-uuid-here")
    
    # Delete the call
    call.delete()
    ```

    </TabItem>
    <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
    </TabItem>
    <TabItem value="service_api" label="HTTP API">
    To delete a call using the Service API, you can make a request to the [`/calls/delete`](../../reference/service-api/calls-delete-calls-delete-post.api.mdx) endpoint.

    ```bash
    curl -L 'https://trace.wandb.ai/calls/delete' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json' \
    -d '{
        "project_id": "string",
        "call_ids": [
            "string"
        ],
    }'
    ```
    </TabItem>
</Tabs>

## Querying & Exporting Calls

<DesktopWindow 
  images={[
    TracingCallsFilterImage,
  ]}
  alt="Screenshot of many calls"
  title="Weave Calls"
/>

The `/calls` page of your project ("Traces" tab) contains a table view of all the Calls in your project. From there, you can:
* Sort
* Filter
* Export

![Calls Table View](../../../static/img/export_modal.png)

The Export Modal (shown above) allows you to export your data in a number of formats, as well as shows the Python & CURL equivalents for the selected calls!
The easiest way to get started is to construct a view in the UI, then learn more about the export API via the generated code snippets.


<Tabs groupId="client-layer">
    <TabItem value="python_sdk" label="Python">
    To fetch calls using the Python API, you can use the [`client.calls`](../../reference/python-sdk/weave/trace/weave.trace.weave_client.md#method-calls) method:

    ```python
    import weave

    # Initialize the client
    client = weave.init("your-project-name")

    # Fetch calls
    calls = client.get_calls(filter=...)
    ```

    :::info[Notice: Evolving APIs]
    Currently, it is easier to use the lower-level [`calls_query_stream`](../../reference/python-sdk/weave/trace_server_bindings/weave.trace_server_bindings.remote_http_trace_server#method-calls_query_stream) API as it is more flexible and powerful.
    In the near future, we will move all functionality to the above client API.

    ```python
    import weave

    # Initialize the client
    client = weave.init("your-project-name")

    calls = client.server.calls_query_stream({
        "project_id": "",
        "filter": {},
        "query": {},
        "sort_by": [],
    })
    ```
    :::
    </TabItem>
    <TabItem value="typescript" label="TypeScript">
    To fetch calls using the TypeScript API, you can use the [`client.getCalls`](../../reference/typescript-sdk/weave/classes/WeaveClient#getcalls) method.
    ```typescript
    import * as weave from 'weave'

    // Initialize the client
    const client = await weave.init('intro-example')

    // Fetch calls
    const calls = await client.getCalls(filter=...)
    ```
    </TabItem>
    <TabItem value="service_api" label="HTTP API">
    The most powerful query layer is at the Service API. To fetch calls using the Service API, you can make a request to the [`/calls/stream_query`](../../reference/service-api/calls-query-stream-calls-stream-query-post.api.mdx) endpoint.

    ```bash
    curl -L 'https://trace.wandb.ai/calls/stream_query' \
    -H 'Content-Type: application/json' \
    -H 'Accept: application/json' \
    -d '{
    "project_id": "string",
    "filter": {
        "op_names": [
            "string"
        ],
        "input_refs": [
            "string"
        ],
        "output_refs": [
            "string"
        ],
        "parent_ids": [
            "string"
        ],
        "trace_ids": [
            "string"
        ],
        "call_ids": [
            "string"
        ],
        "trace_roots_only": true,
        "wb_user_ids": [
            "string"
        ],
        "wb_run_ids": [
            "string"
        ]
    },
    "limit": 100,
    "offset": 0,
    "sort_by": [
        {
        "field": "string",
        "direction": "asc"
        }
    ],
    "query": {
        "$expr": {}
    },
    "include_costs": true,
    "include_feedback": true,
    "columns": [
        "string"
    ],
    "expand_columns": [
        "string"
    ]
    }'
    ```
    </TabItem>
</Tabs>

{/* ## Compare Calls

:::info[Comming Soon]
::: */}

## Call FAQ

{/* TODO:
Common Questions / Variations:
* Images
* Ops
* Cost?
* General data model
*/}

#### Call Schema

Please see the [schema](../../reference/python-sdk/weave/trace_server/weave.trace_server.trace_server_interface#class-callschema) for a complete list of fields.


| Property | Type | Description |
|----------|------|-------------|
| id | string (uuid) | Unique identifier for the call |
| project_id | string (optional) | Associated project identifier |
| op_name | string | Name of the operation (can be a reference) |
| display_name | string (optional) | User-friendly name for the call |
| trace_id | string (uuid) | Identifier for the trace this call belongs to |
| parent_id | string (uuid) | Identifier of the parent call |
| started_at | datetime | Timestamp when the call started |
| attributes | Dict[str, Any] | User-defined metadata about the call |
| inputs | Dict[str, Any] | Input parameters for the call |
| ended_at | datetime (optional) | Timestamp when the call ended |
| exception | string (optional) | Error message if the call failed |
| output | Any (optional) | Result of the call |
| summary | Optional[SummaryMap] | Post-execution summary information |
| wb_user_id | Optional[str] | Associated Weights & Biases user ID |
| wb_run_id | Optional[str] | Associated Weights & Biases run ID |
| deleted_at | datetime (optional) | Timestamp of call deletion, if applicable |

The table above outlines the key properties of a Call in Weave. Each property plays a crucial role in tracking and managing function calls:

- The `id`, `trace_id`, and `parent_id` fields help in organizing and relating calls within the system.
- Timing information (`started_at`, `ended_at`) allows for performance analysis.
- The `attributes` and `inputs` fields provide context for the call, while `output` and `summary` capture the results.
- Integration with Weights & Biases is facilitated through `wb_user_id` and `wb_run_id`.

This comprehensive set of properties enables detailed tracking and analysis of function calls throughout your project.


Calculated Fields:
    * Cost
    * Duration
    * Status

</doc><doc title="tracking"># Tracing

Weave provides powerful tracing capabilities to track and version objects and function calls in your applications. This comprehensive system enables better monitoring, debugging, and iterative development of AI-powered applications, allowing you to "track insights between commits."

## Key Tracing Features

Weave's tracing functionality comprises three main components:

### Calls

[Calls](/guides/tracking/tracing) trace function calls, inputs, and outputs, enabling you to:
- Analyze data flow through your application
- Debug complex interactions between components
- Optimize application performance based on call patterns

### Ops

[Ops](/guides/tracking/ops) are automatically versioned and tracked functions (which produce Calls) that allow you to:
- Monitor function performance and behavior
- Maintain a record of function modifications
- Ensure experiment reproducibility

### Objects

[Objects](/guides/tracking/objects) form Weave's extensible serialization layer, automatically versioning runtime objects (often the inputs and outputs of Calls). This feature allows you to:
- Track changes in data structures over time
- Maintain a clear history of object modifications
- Easily revert to previous versions when needed

By leveraging these tracing capabilities, you can gain deeper insights into your application's behavior, streamline your development process, and build more robust AI-powered systems.</doc></docs></project>
