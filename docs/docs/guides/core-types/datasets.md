import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Datasets

`Dataset`s enable you to collect examples for evaluation and automatically track versions for accurate comparisons. Use this to download the latest version locally with a simple API.

This guide will show you how to:

- Publish `Dataset`s to W&B
- Download the latest version
- Iterate over examples

## Quickstart

<Tabs groupId="programming-language" queryString>
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
</Tabs>

## Alternate constructors

<Tabs groupId="programming-language" queryString>
  <TabItem value="python" label="Python" default>
  Datasets can also be constructed from common Weave objects like `list[Call]`, which is useful if you want to run an evaluation on a handful of examples.

```python
@weave.op
def model(task: str) -> str:
    return f"Now working on {task}"

res1, call1 = model.call(task="fetch")
res2, call2 = model.call(task="parse")

dataset = Dataset.from_calls([call1, call2])
# Now you can use the dataset to evaluate the model, etc.
```

  </TabItem>
  <TabItem value="typescript" label="TypeScript">
  
  ```typescript
  This feature is not available in TypeScript yet.  Stay tuned!
  ```
  </TabItem>
</Tabs>
