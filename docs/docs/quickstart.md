import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Log a trace

<!-- TODO: Update wandb.me/weave-quickstart to match this new link -->

Follow these steps to track your first call

:::tip
You can try the Quickstart as a Jupyter Notebook.
<a class="vertical-align-colab-button" target="_blank" href="http://wandb.me/weave_colab"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>
:::

## 1. Prerequisites

### Install weave

First, install the `weave` library:

<Tabs groupId="programming-language" queryString>
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

### Create a W&B account 

Next, create a Weights & Biases (W&B).
1. Navigate to [https://wandb.ai](https://wandb.ai).
2. Click **Sign Up**.
3. In the sign-up modal, enter an email and password, or use one of the available authentication providers.

### Get your API key

Once you've created your account, copy and set you W&B API key:

1. Navigate to [https://wandb.ai/authorize](https://wandb.ai/authorize).
2. Copy your API key.
3. Set the API key as to the `WANDB_API_KEY` environment variable.

## 2. Log a trace to a new project

To track LLM calls

1. Import the `weave` library
2. Call `weave.init('project-name')`. You will be prompted to log in with your API key if you are not yet logged in on your machine.

    :::tip
    To log to a specific W&B Team name, replace `project-name` with `team-name/project-name`
    :::

3. Add the `@weave.op()` decorator to the python functions you want to track

:::important
In the following example, you will need an OpenAI [API key](https://platform.openai.com/docs/quickstart/step-2-setup-your-api-key).
:::

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
    ```python
    # highlight-next-line
    import weave
    from openai import OpenAI

    client = OpenAI()

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

## 4. View traces in the UI

🎉 Congrats! Now, every time you call this function, `weave` automatically captures the input and output data, and logs any changes made to the code.

![Weave Trace Outputs 1](../static/img/tutorial_trace_1.png)

## What's next?

- Follow the [Tracking flows and app metadata](/tutorial-tracing_2) to start tracking and the data flowing through your app.
