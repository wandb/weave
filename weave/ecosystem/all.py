import importlib
import logging
import os
import typing
from collections import defaultdict, Counter
from weave import context_state

logger = logging.getLogger(__name__)

loading_builtins_token = context_state.set_loading_built_ins()

ALL_MODULES = (
    "example",
    "bertviz",
    "xgboost",
    "shap",
    "sklearn",
    "torchvision",
    "torch_mnist_model_example",
    "huggingface",
    "craiyon",
    "spacy",
    "lens",
    "wandb",
    "scenario",
    "shawn",
    "replicate",
    "openai",
    "py",
    "langchain",
    "umap",
    "hdbscan",
)

LOAD_RESULTS: typing.DefaultDict[str, list[str]] = defaultdict(list[str])

try:
    logger.info("Loading weave.ecosystem")
    for module in ALL_MODULES:
        try:
            globals()[module] = importlib.import_module(f"weave.ecosystem.{module}")
            LOAD_RESULTS["loaded"].append(module)
        except ImportError as exc:
            logger.debug(f"  {module} extension is unavailable, missing {exc.name}")
            LOAD_RESULTS["unavailable"].append(module)
        except Exception as exc:
            logger.error(f"  Error loading {module}")
            logger.error(exc)
            LOAD_RESULTS["error"].append(module)
    for result in ("loaded", "unavailable", "error"):
        modules = ", ".join(LOAD_RESULTS[result]) or "None"
        logger.info(f"  {result}: {modules}")

finally:
    context_state.clear_loading_built_ins(loading_builtins_token)
