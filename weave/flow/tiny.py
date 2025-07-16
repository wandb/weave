from itertools import tee
import tempfile
from weave.flow.dataset import Dataset
from weave.flow.model import Model
from weave.trace.op import Op
from weave.trace.refs import Ref
from weave.trace.context.weave_client_context import require_weave_client
from weave.flow.eval import Evaluation
import asyncio
from typing import Any
from py_irt.training import IrtModelTrainer
from py_irt.config import IrtConfig
from py_irt.dataset import Dataset as PyIrtDataset
import pandas as pd
from weave.flow.scorer import Scorer
from uuid import uuid4
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import pairwise_distances

from weave.trace.vals import WeaveObject
from weave.trace.weave_client import WeaveClient


async def _run_evaluation_for_model(
    model: Model, 
    dataset: Dataset,
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
        name=f"tinify_eval_{name}",
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

async def run_all_evaluations(dataset: Dataset, models: list[Model], scorer: Scorer, scorer_key: str = "score") -> dict[WeaveObject, list[WeaveObject]]:
    """Run all evaluations concurrently."""
    client = require_weave_client()

    # Create evaluation tasks for all models
    evaluation_names = [str(uuid4()) for _ in models]
    evaluation_tasks = [_run_evaluation_for_model(model, dataset, scorer, name) for model, name in zip(models, evaluation_names)]
    # Run all evaluations concurrently
    evaluations = await asyncio.gather(*evaluation_tasks, return_exceptions=True)
    # results is now a list of evaluations
    eval_target = evaluations[-1]
    eval_dict = {call.inputs['self'].name : call for call in eval_target.evaluate.calls()}
    # for every eval in the eval_dict get all the child calls:
    train_da_fool_input = {eval_id : get_results_in_sorted_order(eval, type(scorer).__name__, scorer_key, client) for eval_id, eval in eval_dict.items()}
    client.finish()
    return train_da_fool_input


def get_results_in_sorted_order(eval: WeaveObject, scorer_name: str, scorer_key: str, client: WeaveClient) -> list[WeaveObject]:
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
    results_ordered = [x.output.unwrap()['scores'][scorer_name][scorer_key] for x in calls_ordered]
    return results_ordered

def marshall_Y_dict_into_pandas(Y: dict) -> tuple[pd.DataFrame, str, list[str]]:
    """
    Y is a dict of format: {subject_id: [score1, score2, ...]}
    Return a pandas dataframe of the following format:
        df = pd.DataFrame({
            'user_id': ["joe", "sarah", "juan", "julia"],
            'item_1': [0, 1, 1, 1],
            'item_2': [0, 1, 0, 1],
            'item_3': [1, 0, 1, 0],
        })
    where item_1 is the *first* index of the score list (and so on)

    RETURNS:
        - df: pandas dataframe
        - subject_column_name: name of the subject column
        - item_ids: list of item ids
    """
    # user_ids are the keys of Y
    user_ids = list(Y.keys())
    # Find the max number of items (score list length)
    max_items = max(len(scores) for scores in Y.values()) if Y else 0
    # Build a dict for DataFrame
    data = {'user_id': user_ids}
    for i in range(max_items):
        data[f'item_{i+1}'] = [Y[user_id][i] if i < len(Y[user_id]) else None for user_id in user_ids]
    df = pd.DataFrame(data)
    return df, "user_id", [f'item_{i+1}' for i in range(max_items)]


def train_irt_model(evaluation_results: dict[str, list[float]], **kwargs: Any) -> IrtModelTrainer:
    """
    Y is a dict of format: {subject_id: [score1, score2, ...]}

    kwargs are passed to the IrtConfig constructor
    """

    df, subject_column_name, item_ids = marshall_Y_dict_into_pandas(evaluation_results)
    pyirt_dataset = PyIrtDataset.from_pandas(df, subject_column_name, item_ids)

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
    data_path = tempfile.TemporaryDirectory()
    trainer = IrtModelTrainer(config=configuration, dataset=pyirt_dataset, data_path=data_path.name)
    trainer.train()

    return trainer

def make_dataset(dataset, anchor_ids, A, B, anchor_weights, name = None, description = None):
    """
    A,B are of shape (.., .., len(dataset))
    anchor_ids is of shape (len(tiny_items))
    anchor_weights is of shape (len(tiny_items)) == len(anchor_ids)

    Adds three keys to the dataset:
        - A_anchor: the anchor discrimination
        - B_anchor: the anchor difficulty
        - w_anchor: the anchor weight
    """
    ret_dataset = []
    for i, anchor in enumerate(anchor_ids):
        row = dataset[i]
        ret_dataset.append({
            **row,
            "A_anchor": A[:, :, anchor],
            "B_anchor": B[:, :, anchor],
            "w_anchor": anchor_weights[i] # w_anchor is of len(anchor_ids)
        })
    dataset = Dataset(
        name=name,
        description=description,
        rows=ret_dataset
    )
    return dataset


def tiny_dataset(dataset: Dataset, results: dict[str, list[float]], trained_irt_model: IrtModelTrainer, num_items: int=100) -> Dataset:
    num_items = min(num_items, len(dataset))
    # results is the dict from run_all_evaluations
    balance_weights = np.ones(len(list(results.values())[0])) # we weight each value equally
    A, B = np.array(trained_irt_model.best_params['disc']).T[None, :, :], np.array(trained_irt_model.best_params['diff']).T[None, :, :]
    X = np.vstack((A.squeeze(), B.squeeze())).T
    kmeans = KMeans(n_clusters=num_items, n_init='auto')
    kmeans.fit(X)
    anchor_points = pairwise_distances(kmeans.cluster_centers_, X, metric='euclidean').argmin(axis=1)
    norm_balance_weights = balance_weights / balance_weights.sum()
    anchor_weights = np.array([np.sum(norm_balance_weights[kmeans.labels_==c]) for c in range(num_items)])

    return make_dataset(dataset, anchor_points, A, B, anchor_weights, name=f"{dataset.name}_tiny_{num_items}", description=f"tiny dataset with {num_items} items")

def tinyify(dataset_ref: Ref, models: list[Model], scorer: Scorer, num_items: int=100) -> Ref | None:
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
        sorted_dataset = _create_dataset_ordering(dataset)
    except Exception as e:
        raise ValueError(f"Failed to retrieve dataset from ref {dataset_ref.uri()}: {e}")
    
    # Execute all evaluations concurrently
    evaluation_results = asyncio.run(run_all_evaluations(sorted_dataset, models, scorer))
    
    client.finish()

    # TODO: transform from list of evals
    # {"model1": [0.3, 1.0, ...], "model2": [1.0, 0.0, ...]}
    # TODO: train the irt model
    irt_model = train_irt_model(evaluation_results)

    # TODO: produce dataset from irt_model.best_params
    teenytiny = tiny_dataset(dataset, evaluation_results, irt_model, num_items)

    # TODO: save dataset to weave
    # TODO: run evaluations for models against tiny dataset
    client._save_object(teenytiny, teenytiny.name, "latest")

    # TODO: return ref to tiny, D eval results, d eval results
    return None

