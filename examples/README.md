# Weave Examples

## Examples structure 

The `examples/` folder contains:
* `apps/`: the most polished demos--best place for a quick overview
* `tutorial/`: more detailed walkthroughs for a growing set of use cases 
* `reference/`: syntax and usage for Weave types, ops, and panels

Notebooks outside of these folders area range from focused proofs-of-concept to very experimental works-in-progress. We hope these support and inspire your exploration, and 

## Running examples

### Locally with Jupyter notebook

Run `jupyter notebook` or `jupyter lab` in the root directory `examples`, and then use the Jupyter browser to open and run them.

### Google Colab

Run the same code in a Google Colab, making sure to install Weave from PyPi first with `!pip install weave`.
Colabs to get started:
* [Weave Quickstart](https://colab.research.google.com/drive/1TwlhvvoWIHKDtRUu6eW0NMRq0GzGZ9oX)
* [Weave Board Quickstart: Generative AI Playground](https://colab.research.google.com/drive/1gcR-ucIgjDbDEBFykEpJ3kkBoBQ84Ipr)

## Recommended examples

### Get started

- [Weave quickstart](../examples/apps/weave_demo_quickstart.ipynb)
- [View and transform images](../examples/tutorial/images_gen.ipynb)
- [Train MNIST and visualize predictions](../examples/tutorial/mnist_train.ipynb)

### Weave fundamentals

- [End-to-end walkthrough](../examples/Weave%20demo.ipynb)
- [Create Weave Ops](../examples/reference/create_ops.ipynb)
- [Organize Weave Panels](../examples/tutorial/layout_panels.ipynb)

### Build interactive Weave Boards

- in Google Colab: [Weave Board Quickstart: Generative AI Playground](https://colab.research.google.com/drive/1gcR-ucIgjDbDEBFykEpJ3kkBoBQ84Ipr)
- [Monitor time-series data](../examples/app/Monitor.ipynb)
- [Visual storytelling](../examples/experimental/skip_test/Diffusion%20explore.ipynb)
- [Remix art](../examples/app/art_explore.ipynb)

### Explore the Ecosystem

- [BertViz: Visualize attention in transformers](../examples/bert_viz.ipynb)
- [Browse HuggingFace datasets](../examples/tutorial/huggingface_datasets.ipynb)
- [Generate images with Craiyon](../examples/tutorial/image_gen_craiyon.ipynb)
- [Generate images with Replicate](../examples/experimental/skip_test/image_gen_replicate.ipynb)
