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
    eval_table_columns = {
        "dataset_id": weave.WeaveList([r["id"] for r in ds_rows]),
        "output": weave.WeaveList(outputs),
        **eval_result["columns"],
    }
    return {
        "summary": summary,
        "eval_table": weave.WeaveList(eval_table_columns),
    }
