# Weave Examples

## Examples structure

The `examples/` folder contains:

- `get_started.ipynb`: a quick interactive notebook overview of Weave
- `getting_started`: Learn how to build interactive data applications
- `reference`: Syntax and usage for Weave types, ops, and panels
- `monitoring`: Examples and documentation for LLM monitoring
- `experimental`: Everything else, ranging from focused proofs-of-concept to very experimental works-in-progress—we hope these inspire your exploration and welcome PRs for improvement!
- `apps`: Example applications
- `guides (future)`: Guides to use specific features for advanced users

## Running examples

### Locally with Jupyter notebook

Run `jupyter notebook` or `jupyter lab` in the root directory `examples`, and then use the Jupyter browser to find and open.

### Google Colab

Run the same code in a Google Colab, making sure to install Weave from PyPi first with `!pip install weave`.

Colabs to get started:

- [Weave Quickstart](https://colab.research.google.com/drive/1TwlhvvoWIHKDtRUu6eW0NMRq0GzGZ9oX)
- [Weave Board Quickstart: Generative AI Playground](https://colab.research.google.com/drive/1gcR-ucIgjDbDEBFykEpJ3kkBoBQ84Ipr)

## Recommended examples

### Get started

- [Weave quickstart](../examples/getting_started/0_weave_demo_quickstart.ipynb)
- [View and transform images](../examples/getting_started/2_images_gen.ipynb)
- [Train MNIST and visualize predictions](../examples/experimental/mnist_train.ipynb)

### LLM Monitoring

- [OpenAI API Usage Board](../examples/prompts/llm_monitoring/openai_client_quickstart.ipynb)

### Weave fundamentals

- [End-to-end walkthrough](../examples/getting_started/1_weave_demo.ipynb)
- [Create Weave Ops](../examples/reference/create_ops.ipynb)
- [Organize Weave Panels](../examples/experimental/layout_panels.ipynb)

### Build interactive Weave Boards

- in Google Colab: [Weave Board Quickstart: Generative AI Playground](https://colab.research.google.com/drive/1gcR-ucIgjDbDEBFykEpJ3kkBoBQ84Ipr)
- [Monitor time-series data](../examples/experimental/Monitor.ipynb)
- [Visual storytelling](../examples/experimental/skip_test/Diffusion%20explore.ipynb)
- [Remix art](../examples/experimental/skip_test/art_explore.ipynb)

### Explore the Ecosystem

- [Browse HuggingFace datasets](../examples/experimental/huggingface_datasets.ipynb)
- [Generate images with Craiyon](../examples/experimental/image_gen_craiyon.ipynb)
- [Generate images with Replicate](../examples/experimental/skip_test/image_gen_replicate.ipynb)
