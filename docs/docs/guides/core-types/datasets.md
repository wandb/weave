---
sidebar_position: 2
hide_table_of_contents: true
---

# Datasets

`Dataset`s enable you to collect examples for evaluation and automatically track versions for accurate comparisons.
Easily update datasets with the UI and download the latest version locally with a simple API.

This guide will show you how to:
- Publish `Dataset`s to W&B
- Download the latest version
- Iterate over examples

## Sample code

```python
import weave
# Initialize Weave
weave.init('intro-example')

# Create a dataset
dataset = weaveflow.Dataset([
    {'id': '0', 'sentence': "He no likes ice cream.", 'correction': "He doesn't like ice cream."},
    {'id': '1', 'sentence': "She goed to the store.", 'correction': "She went to the store."},
    {'id': '2', 'sentence': "They plays video games all day.", 'correction': "They play video games all day."}
])

# Publish the dataset
weave.publish(dataset, 'grammar')

# Retrieve the dataset
dataset_ref = weave.ref('grammar').get()

# Access a specific example
example_label = dataset_ref.rows[2]['label']
```
