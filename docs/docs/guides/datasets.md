# Datasets

`Dataset`s enable you to collect examples for evaluation and automatically track versions for accurate comparisons. Use this to download the latest version locally with a simple API.

This guide will show you how to:

- Publish `Dataset`s to W&B
- Download the latest version
- Iterate over examples

## Sample code

```python
import weave
from weave import Dataset
# Initialize Weave
weave.init('intro-example')

# Create a dataset
dataset = Dataset(name='grammar', rows=[
    {'id': '0', 'sentence': "He no likes ice cream.", 'correction': "He doesn't like ice cream."},
    {'id': '1', 'sentence': "She goed to the store.", 'correction': "She went to the store."},
    {'id': '2', 'sentence': "They plays video games all day.", 'correction': "They play video games all day."}
])

# Publish the dataset
weave.publish(dataset)

# Retrieve the dataset
dataset_ref = weave.ref('grammar').get()

# Access a specific example
example_label = dataset_ref.rows[2]['sentence']
```
