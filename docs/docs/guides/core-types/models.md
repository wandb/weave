import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Models

A `Model` is a combination of data (which can include configuration, trained model weights, or other information) and code that defines how the model operates. By structuring your code to be compatible with this API, you benefit from a structured way to version your application so you can more systematically keep track of your experiments.

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
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

    ## Pairwise evaluation of models

    When [scoring](../evaluation/scorers.md) models in a Weave [evaluation](../core-types/evaluations.md), absolute value metrics (e.g. `9/10`) are typically less useful than relative ones (e.g. Model A performs better than Model B). _Pairwise evaluation_ allows you to compare the outputs of two models by ranking them relative to each other. This approach is particularly useful when you want to determine which model performs better for subjective tasks such as text generation, summarization, or question answering. With pairwise evaluation, you can obtain a relative preference ranking that reveals which model is best for specific inputs.

    The following code sample demonstrates how to implement a pairwise evaluation in Weave by createing a [class-based scorer](../evaluation/scorers.md#class-based-scorers) called `PairwiseScorer`. The `PairwiseScorer` compares two models, `ModelA` and `ModelB`, and returns a relative score of the model outputs based on explicit hints in the input text.

    ```python
    from weave import Model, Evaluation, Scorer

    class ModelA(Model):
        @weave.op
        def predict(self, input_text: str):
            if "Prefer model A" in input_text:
                return {"response": "This is a great answer from Model A"}
            return {"response": "Meh, whatever"}

    class ModelB(Model):
        @weave.op
        def predict(self, input_text: str):
            if "Prefer model B" in input_text:
                return {"response": "This is a thoughtful answer from Model B"}
            return {"response": "I don't know"}

    class PreferenceScorer(Scorer):
        @weave.op
        async def score(self, output: dict, input_text: str) -> dict:
            other_output = await self._get_other_model_output(
                {"input_text": input_text}
            )
            if other_output is None:
                return {"primary_is_better": False, "reason": "Other model failed"}

            if "Prefer model A" in input_text:
                primary_is_better = True
                reason = "Model A gave a great answer"
            else:
                primary_is_better = False
                reason = "Model B is preferred for this type of question"

            return {"primary_is_better": primary_is_better, "reason": reason}

    dataset = Dataset(
        rows=[
            {"input_text": "Prefer model A: Question 1"},  # Model A wins
            {"input_text": "Prefer model A: Question 2"},  # Model A wins
            {"input_text": "Prefer model B: Question 3"},  # Model B wins
            {"input_text": "Prefer model B: Question 4"},  # Model B wins
        ]
    )

    model_a = ModelA()
    model_b = ModelB()
    pref_scorer = PreferenceScorer(other_model=model_b)
    evaluation = Evaluation(dataset=dataset, scorers=[pref_scorer])
    evaluation.evaluate(model_a)
```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
    ```plaintext
    This feature is not available in TypeScript yet.  Stay tuned!
    ```
  </TabItem>
</Tabs>
