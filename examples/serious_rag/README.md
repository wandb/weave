# RAG Demowith Weave
This repo aims at demonstraing the continuous development and improvement of a RAG model with Weave.

### Getting Started
1. Install `requirements_verbose.txt` in environment (for Mac Silicon)
2. Setup `benchmark.env` in `./config` with necessary API keys (`WANDB_API_KEY`) and optional (`HUGGINGFACEHUB_API_TOKEN`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
3. Set variables accordingly in `general_config.yaml`
    - Set Entity, Project (device for now only CPU)
    - Setup = True the first time to run to extract data and generate dataset
    - The chat model, embedding model, judge model, prompts, params as you want to!
4. Run `main.py`

### Code Structure
- `main.py` - contains the main application flow - serves as an example for bringing everything together
- `setup.py` - contains utility functions for the RAG model `RagModel(weave.Model)` and the data extraction and dataset generation functions
- `evaluatie.py` - contains the `weave.flow.scorer.Scorer` classes to evaluate the correctness, hallucination, and retrieval performance.
- `./configs` - the configs of the project
    - `./configs/benchmark.env` - should contain env vars for your W&B account and the model providers you want to use (HuggingFace, OpenAI, Anthropic, Mistral, etc.)
    - `./configs/requirements.txt` - environment to install necessary dependencies to run RAG
    - `./configs/sources_urls.csv` - a CSV to contain all the Websites and PDFs that should be considered by RAG
    - `./configs/general_config.yaml` - the central config file with models, prompts, params
- `annotate.py` - can be run with `streamlit run annotation.py` to annotate existing datasets or fetch datasets based on production function calls to annotate and save as new dataset.

## Scenario 1 - No Model Training only W&B Weave
Weave is a toolkit for teh development of GenAI applications that is targeted at Software Engineers and ML Engineers with a focus on Software Development. In the first scenario we consider the case where no model training or finetuning is conducted by AI APIs (e.g. OpenAI, Mistral, HuggingFace) to develop an application. 

- **Use-Case:** Climate Q&A RAG Chatbot on PDFs and Websites    
- **Weave Workflow:** The following steps show how Weave was integrated in this codebase
    1. Optional Setup (see `setup` bool in `./configs/general_config.yaml`)
        - Extract data from sources with `setup.download_source_docs`
            - **Weave**: define function as `@weave.op()` to trace input config and to Op tab
            - **Weave**: extract data and publish `weave.Dataset` to use in next step and ad to Dataset tab
        - Generate synthetic dataset to evaluate chatbot on with `setup.gen_data`
            - **Weave**: define function as `@weave.op()` to trace input config and calls to model APIs
            - **Weave**: generate dataset using LLMs and publish `weave.Dataset` to use for eval
    2. Optional Evaluation (see `benchmark` bool in `./configs/general_config.yaml`)
        - Create `RagModel(weave.Model)` that will download and create a chat model and VDB
            - **Weave**: Define RagModel as child class from `weave.Model` and define `predict` function with `@weave.op()` to trace configs and add to Model tab. Since the parent class `weave.Model` inherits from a pydantic base class in order to define a dynamic attribute we can introduce a custom `@validator` or we can create a custom `__init__` constructing the model from the other attributes calling `super.__init__(**data)` only at the end. Just passing in a model object of type `typing.Any` is also possible but will not show the config params fully decoded in Weave. A `weave.Model` also has to have either a `predict/infer/forward` function with the weave operator. It can be declared async but doesn't have to. 
        - Start a `weave.Evaluation` that takes evaluates model on the generated dataset based on correctness, hallucination, and retrieval perforamnce.
            - **Weave:** Create a `weave.Evaluation` object passing in a list of dicts or a `weave.Dataset` object and a serious of scoring functions `@weave.op()` or classes `weave.flow.scorer.Scorer`. Here we define two new `Scorer` Judges and overwrite the `score` function while also decorating it with `@weave.op()` to track each call. We take the standard `summarize` function of the scorer base class which will simply aggregate the boolean vector that was produced running score on each of the rows in the dataset.
            - **Weave:** We call `asyncio.run(evaluation.evaluate(wf_rag_model))` on the specific model. This will always have to be called with `asyncio` even if the predict functions in the used models are not async because of the way the Evaluator is defined. Since jupyter notebooks already have their dedicated event loops only calling `await evaluation.evaluate(model)` will suffice.

## Scenario 2 - Model Training with W&B Models
Assuming that MLEs wouldn't only do SWE work they would also be tasked with fine-tuning and/or building from scratch we could assuume that they wouldn't be using Weave as a standalone solution but also work with the W&B Models offering.

- **Use-Case:** Climate Q&A RAG Chatbot on PDFs and Websites
- **Weave and W&B Models Workflow:** Ideas for now TBD
    - Access Registry (datasets, models) from Models
    - Start Streamlit Annotation program as easy example of more elaborate annotation flows ⇒ privacy is the main problem for prod mon then (except if we get prod mon through dedicated service an as an artifact from models e.g.)
    - Even for sweeps I wouldn’t have change anything - the traces would simply go to Weave 👍

