from weave.flow.dataset import Dataset
from weave.flow.model import Model
from weave.trace.refs import Ref
from weave.trace.context.weave_client_context import require_weave_client
from weave.flow.eval import Evaluation
import asyncio
from typing import Any
from py_irt.training import IrtModelTrainer
from py_irt.config import IrtConfig
from py_irt.dataset import Dataset as PyIrtDataset
import pandas as pd
import json
import os
from collections import defaultdict
from weave.flow.scorer import Scorer
from uuid import uuid4

from weave.trace.vals import WeaveObject
from weave.trace.weave_client import WeaveClient


async def _run_evaluation_for_model(
    model: Model, 
    dataset: Any,
    scorer: Scorer,
    name: str,
) -> Evaluation | None:
    """
    Run evaluation for a single model.
    
    Args:
        model: The model to evaluate.
        dataset: The dataset to evaluate against.
        model_index: Index of the model for naming purposes.
        
    Returns:
        evaluation uri 
    """
    client = require_weave_client()
    # Create a new evaluation instance for each model for clean separation
    evaluation = Evaluation(
        dataset=dataset, 
        scorers=[scorer],
        evaluation_name=f"tinify_eval_{name}",
    )
    
    # Run the evaluation asynchronously
    await evaluation.evaluate(model)
    client.flush()

    return evaluation

def _create_dataset_ordering(dataset: Any) -> Dataset:
    """
    Create a dataset ordering from the dataset.
    """
    new_rows = []
    for row in dataset.rows:
        new_row = {**row, "_uuid": uuid4()}
        new_rows.append(new_row)

    new_rows_sorted = sorted(new_rows, key=lambda x: x["_uuid"])
    return Dataset(rows=new_rows_sorted, name=dataset.name, description=dataset.description)

async def run_all_evaluations(dataset: Any, models: list[Model], scorer: Scorer) -> dict[WeaveObject, list[WeaveObject]]:
    """Run all evaluations concurrently."""
    client = require_weave_client()

    new_dataset = _create_dataset_ordering(dataset)
    # Create evaluation tasks for all models
    evaluation_names = [str(uuid4()) for _ in models]
    evaluation_tasks = [ _run_evaluation_for_model(model, new_dataset, scorer, name) for model, name in zip(models, evaluation_names)]
    # Run all evaluations concurrently
    evaluations = await asyncio.gather(*evaluation_tasks, return_exceptions=True)
    # results is now a list of evaluations
    eval_target = evaluations[-1]
    eval_dict = {call.inputs['self'].name : call for call in eval_target.evaluate.calls()}
    # for every eval in the eval_dict get all the child calls:
    train_da_fool_input = {eval_id : get_results_in_sorted_order(eval, scorer.__name__, client) for eval_id, eval in eval_dict.items()}
    client.finish()
    return train_da_fool_input


def get_eval_by_uri(uri: str, client: WeaveClient) -> WeaveObject:
    """
    Get the eval id from the uri.
    """
    calls = client.get_calls(
        filter={"op_names": [uri]},
        sort_by=[{"field": "created_at", "direction": "desc"}],
        limit=1,
    )
    return calls[0]

def get_results_in_sorted_order(eval: WeaveObject, scorer_name: str, client: WeaveClient) -> list[WeaveObject]:
    """
    Get the results in sorted order.
    """
    calls = client.get_calls(
        filter={"parent_ids": [eval.id]},
        sort_by=[{"field":"started_at","direction":"desc"}],
    )
    eval_result_calls = [x for x in calls if "predict_and_score" in x.op_name] # TODO: this is a hack
    
    # first I sort the call_order:
    calls_ordered = sorted(eval_result_calls, key=lambda x: x.inputs.unwrap()['example']['_uuid'])
    # then I get the results in the same order:
    results_ordered = [x.output.unwrap()['scores'][scorer_name] for x in calls_ordered]
    return results_ordered

def tinyify(dataset_ref: Ref, models: list[Model], scorer: Scorer) -> Ref | None:
    """
    Execute evaluations against the dataset for each model in models concurrently.
    
    Args:
        dataset_ref: The dataset reference to evaluate against.
        models: List of models to evaluate against the dataset.
        
    Returns:
        A reference to evaluation results, or None if no models provided.
        
    Raises:
        ValueError: If the dataset reference cannot be resolved or models are invalid.
        
    Examples:
        ```python
        # Execute evaluations for multiple models against a dataset
        dataset_ref = parse_uri("weave:///entity/project/object/my_dataset:digest")
        models = [model1, model2]
        results_ref = tinyify(dataset_ref, models)
        ```
    """
    if not models:
        return None
        
    client = require_weave_client()
    
    # Get the dataset from the dataset reference
    try:
        dataset = client.get(dataset_ref)
    except Exception as e:
        raise ValueError(f"Failed to retrieve dataset from ref {dataset_ref.uri()}: {e}")
    
    # Execute all evaluations concurrently
    evaluations_uris = asyncio.run(run_all_evaluations(dataset, models, scorer))
    
    # Log results summary
    successful_evals = sum(1 for r in evaluation_results if r.get("error") is None)
    total_evals = len(evaluation_results)
    print(f"Completed {successful_evals}/{total_evals} evaluations successfully")
    
    client.finish()

    # TODO: transform from list of evals
    # {"model1": [0.3, 1.0, ...], "model2": [1.0, 0.0, ...]}
    # TODO: train the irt model
    irt_model = train_irt_model(evaluation_results)

    # TODO: produce dataset from irt_model.best_params
    tiny_dataset = tiny_dataset(dataset, irt_model)

    # TODO: save dataset to weave
    # TODO: run evaluations for models against tiny dataset


    # TODO: return ref to tiny, D eval results, d eval results
    return None


def train_irt_model(evaluation_results: dict[str, list[float]], **kwargs: Any) -> IrtModelTrainer:
    """
    Y is a dict of format: {subject_id: [score1, score2, ...]}

    kwargs are passed to the IrtConfig constructor
    """

    df = pd.DataFrame(evaluation_results)
    pyirt_dataset = PyIrtDataset.from_pandas(df, subject_column_name="subject_id", item_ids=["item_id"])

    config_dict = {
        "model_type": "multidim_2pl",
        "dims": 2, # the D value
        "lr": 0.1, # paper value
        "epochs": 2000, # paper value
        "priors": "hierarchical",
        "seed": 42,
        "deterministic": True,
    }
    config_dict.update(kwargs)
    configuration = IrtConfig(**config_dict)

    trainer = IrtModelTrainer(config=configuration, dataset=pyirt_dataset)
    trainer.train()

    return trainer

def tiny_dataset(dataset: Dataset, irt_model: IrtModelTrainer) -> Dataset:
    # TODO: extract anchor points from irt_model.best_params
    # TODO: create a new dataset with the anchor points
    return dataset