import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Get started with Weave

In this quickstart guide, you’ll integrate Weave with the OpenAI API to analyze a sentence for mentions of dinosaurs and extract structured information about their names, common names, and diets.

Before you begin, complete the [prerequisites](#prerequisites).

:::tip
Do you want to test Weave without the setup? Try the Jupyter Notebook.
<a class="vertical-align-colab-button" target="_blank" href="http://wandb.me/weave_colab"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>
:::

## Prerequisites

### Create a W&B account

[Sign up](https://app.wandb.ai/login?signup=true&_gl=1*1km3y5d*_ga*ODEyMjQ4MjkyLjE3MzE0MzU1NjU.*_ga_JH1SJHJQXJ*MTczNjM2ODMwMi4xNDIuMS4xNzM2MzY4NTczLjYwLjAuMA..*_ga_GMYDGNGKDT*MTczNjM2ODMwMi4xMDQuMS4xNzM2MzY4NTczLjAuMC4w*_gcl_au*OTI3ODM1OTcyLjE3MzE0MzU1NjUuMTgyNTg2NDA2LjE3MzYyMDQ5NDUuMTczNjIwNjI3Mw..) for a free W&B account.

### Get your W&B API key

1. Navigate to [https://wandb.ai/authorize](https://wandb.ai/authorize).
2. Copy your API key.

### Install Weave

Install Weave locally:

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

## 1. Initialize a Weave project and log calls.

Calls are the fundamental construct in Weave, and represent a single execution of a function. Call capture the following information from functions:

- Inputs (arguments)
Outputs (return value)
Metadata (duration, exceptions, LLM usage, etc.)
Calls are similar to spans in the OpenTelemetry data model. A Call can:

Belong to a Trace (a collection of calls in the same execution context)
Have parent and child Calls, forming a tree structure

<Tabs groupId="programming-language">
  <TabItem value="python" label="Python" default>

    1. Import the `weave` library.
    2. Initalize a Weave project using `weave.init()`.
    3. Decorate functions that you want to track in Weave with the `@weave.op()` decorator. 

    In the following example, the `extract_dinos` function processes a sentence provided by the user and returns a JSON object with extracted dinosaur data. Once you run the function, Weave automatically begins tracking the function’s inputs, outputs, and execution details, and provides a link to visualize the trace in the Weave UI. The traces for this function are tracked in a Weave project called `'jurassic-park`.

    :::important
    To use the following code sample, add your [OpenAI API key](https://platform.openai.com/docs/quickstart/step-2-setup-your-api-key).
    :::

    ```python
    # highlight-next-line
    import weave
    from openai import OpenAI

    client = OpenAI()

    # Weave tracks the inputs, outputs and code of this function
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


    # Initialise the Weave project
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

- Follow the [Tracking flows and app metadata](/tutorial-tracing_2) to start tracking and the data flowing through your app.
