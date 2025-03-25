import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Track app versions

In [Log a trace](/quickstart) and [Track nested functions and metadata](/tutorial-tracing_2), you learned important Weave fundamentals: logging a call to Weave, tracking nested functions, and logging metadata. Building on this, it's critical to understand how modifications to your application code and/or attributes change application outputs. With Weave's `Model` class, you can track application versions, understand how changes between versions affect application behavior, and store and version changing application attribute like model vendor IDs, systme prompts, temperature, and more.

:::important
The `Model` class is currently only available in Python.
:::

In this guide, you'll learn:

- How to use `Model` to track and version your app and its attributes.
- How to export, modify and reuse a `Model` that you've already logged.

## Use `Model` to version an app

To create a `Model`, do the following:

1. Define a class that inherits from `weave.Model`
2. Add type definitions to all class attributes
3. Add a typed `invoke` function with the `@weave.op()` decorator to your class.

When you change the class attributes or the code that defines your model, Weave automatically logs changes and updates the application version. Now, you can easily compare output across different versions of your app.

In the example below, the model name, temperature and system prompt are tracked and versioned using `Model`.

<Tabs groupId="programming-language" queryString>
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

Now, you can instantiate and call the model with `.invoke`:

<Tabs groupId="programming-language" queryString>
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

After calling `.invoke`, you can view the trace in Weave. Now, model attributes are tracked along with model functions that have been decorated with `weave.op()`. You can see the model is also versioned (in the example, `v21`). Click on the model to see all of calls that have used that version of the model.

![Re-using a weave model](../static/img/tutorial-model_invoke3.png)

## Export and reuse a `Model`

Because Weave stores and versions `Model`s that have been invoked, you can export and reuse these models. To do so, complete the following steps:

1. In the Weave UI, navigate to the **Models** tab.
2. In the row for the `Model` with versions that you want to export or reuse, click the contents of the **Versions** column. The available versions display.
3. In the **Object** column, click the name of the `Model` version that you want to reuse or export. A pop-up modal displays.
4. Select the **Use** tab.
5. Under `The ref for this model version is:`, copy the `Model` URI (e.g. `weave:///wandb/weave-intro-notebook/object/OpenAIGrammarCorrector:a21QVEgoDsNJKFHo7FkLd6S2gsf4frMXYMpwX2Qg7sw`).
6. To retrieve the `Model` version for export or resuse, call `weave.ref(<URI>).get()`, replacing `<URI>` with your URI.

The following code examples builds on the example in [ Use `Model` to version an app](#use-model-to-version-an-app), and shows reuse of a  `Model` version specified by `weave:///morgan/jurassic-park/object/ExtractDinos:ey4udBU2MU23heQFJenkVxLBX4bmDsFk7vsGcOWPjY4`.

<Tabs groupId="programming-language" queryString>
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

In the Weave UI, you can now see that the new `Model` version (`v21`) was used with the new input:

![Re-using a weave model](../static/img/tutorial-model_re-use.png)

## What's next?

- Follow the [Build an Evaluation pipeline tutorial](/tutorial-eval) to start iteratively improving your applications.
