import typing
import weave

from .dataset import Dataset
from .model import Model
from .evaluate import Evaluate


@weave.op()
def evaluate(eval: Evaluate, dataset: Dataset, model: Model) -> typing.Any:
    outputs = dataset.rows.apply(lambda r: model.predict(r))  # type: ignore
    eval_result = eval.compute(dataset, outputs)
    summary = eval_result["summary"]

    eval_table_columns: dict[str, weave.WeaveList] = {
        "dataset_id": weave.WeaveList([r["id"] for r in dataset.rows]),
        # For now, put the whole dataset into the eval data. In the future we should put
        # refs instead.
        # TODO: use refs instead
        "dataset": dataset.rows,  # type: ignore
        "output": outputs,
        **eval_result["columns"],
    }
    return {
        "summary": summary,
        "eval_table": weave.WeaveList(eval_table_columns),
    }
