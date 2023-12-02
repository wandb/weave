import typing
import weave

from .dataset import Dataset
from .model import Model
from .evaluate import Evaluate


@weave.op()
def evaluate(eval: Evaluate, dataset: Dataset, model: Model) -> typing.Any:
    outputs = []
    ds_rows = list(dataset.rows)
    for i, row in enumerate(ds_rows):
        print("evaluating row", i)
        try:
            output = model.predict(row)
        except:
            output = None
        outputs.append(output)
    eval_result = eval.compute(dataset, outputs)
    summary = eval_result["summary"]

    dataset_cols = {}
    for col_key in ds_rows[0]:
        dataset_cols[col_key] = weave.WeaveList([r[col_key] for r in ds_rows])

    eval_table_columns: dict[str, weave.WeaveList] = {
        "dataset_id": weave.WeaveList([r["id"] for r in ds_rows]),
        # For now, put the whole dataset into the eval data. In the future we should put
        # refs instead.
        # TODO: use refs instead
        "dataset": ds_rows,
        "output": weave.WeaveList(outputs),
        **eval_result["columns"],
    }
    return {
        "summary": summary,
        "eval_table": weave.WeaveList(eval_table_columns),
    }
