from weave.flow.model import Model
from weave.trace.refs import Ref
from weave.trace.context.weave_client_context import require_weave_client
from weave.flow.dataset import Dataset
from weave.flow.eval import Evaluation
import asyncio
from typing import Any

async def _run_evaluation_for_model(
    model: Model, 
    dataset: Any, 
) -> dict[str, Any]:
    """
    Run evaluation for a single model.
    
    Args:
        model: The model to evaluate.
        dataset: The dataset to evaluate against.
        model_index: Index of the model for naming purposes.
        
    Returns:
        Dictionary containing model, result, and optional error.
    """
    client = require_weave_client()
    try:
        # Create a new evaluation instance for each model for clean separation
        evaluation = Evaluation(
            dataset=dataset, 
            scorers=[],
            evaluation_name=f"tinyify_eval_{getattr(model, 'name', 'model')}"
        )
        
        # Run the evaluation asynchronously
        result = await evaluation.evaluate(model)

        return {
            "model": model,
            "result": result
        }
    except Exception as e:
        # Return error information instead of raising
        return {
            "model": model,
            "result": None,
            "error": str(e)
        }
    finally:
        client.flush()

async def run_all_evaluations(dataset: Any, models: list[Model]) -> list[dict[str, Any]]:
    """Run all evaluations concurrently."""
    client = require_weave_client()
    # Create evaluation tasks for all models
    evaluation_tasks = [
        _run_evaluation_for_model(model, dataset) for model in models
    ]
    
    # Run all evaluations concurrently
    results = await asyncio.gather(*evaluation_tasks, return_exceptions=True)
    
    # Process results to handle any exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Warning: Evaluation failed for model {models[i]}: {result}")
            processed_results.append({
                "model": models[i],
                "result": None,
                "error": str(result)
            })
        else:
            processed_results.append(result)

    client.finish()
    return processed_results


def tinyify(dataset_ref: Ref, models: list[Model]) -> Ref | None:
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
    evaluation_results = asyncio.run(run_all_evaluations(dataset, models))
    
    # Log results summary
    successful_evals = sum(1 for r in evaluation_results if r.get("error") is None)
    total_evals = len(evaluation_results)
    print(f"Completed {successful_evals}/{total_evals} evaluations successfully")
    
    client.finish()

    # For now, return None - in a full implementation this would:
    # 1. Analyze the evaluation results
    # 2. Create a tinyified dataset based on the results
    # 3. Save and return a reference to the tinyified dataset
    return None