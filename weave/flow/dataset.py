from typing import Any, Callable, Union
import time
import traceback

from rich import print
from rich.console import Console
from pydantic import field_validator

import weave
from weave.flow.obj import Object
from weave.trace.vals import TraceTable
from weave.flow.model import Model, get_infer_method
from weave.trace.env import get_weave_parallelism
from weave.trace.errors import OpCallError
from weave.flow.util import async_call, async_foreach

console = Console()

def short_str(obj: Any, limit: int = 25) -> str:
    str_val = str(obj)
    if len(str_val) > limit:
        return str_val[:limit] + "..."
    return str_val


class Dataset(Object):
    """
    Dataset object with easy saving and automatic versioning

    Examples:
        ```
        # Create a dataset
        dataset = Dataset(name='grammar', rows=[
            {'id': '0', 'sentence': "He no likes ice cream.", 'correction': "He doesn't like ice cream."},
            {'id': '1', 'sentence': "She goed to the store.", 'correction': "She went to the store."},
            {'id': '2', 'sentence': "They plays video games all day.", 'correction': "They play video games all day."}
        ])

        # Publish the dataset
        weave.publish(dataset)

        # Retrieve the dataset
        dataset_ref = weave.ref('grammar').get()

        # Access a specific example
        example_label = dataset_ref.rows[2]['sentence']
        ```
    """

    rows: weave.Table

    @field_validator("rows", mode="before")
    def convert_to_table(cls, rows: Any) -> weave.Table:
        if not isinstance(rows, weave.Table):
            table_ref = getattr(rows, "table_ref", None)
            if isinstance(rows, TraceTable):
                rows = list(rows)
            rows = weave.Table(rows)
            if table_ref:
                rows.table_ref = table_ref
        if len(rows.rows) == 0:
            raise ValueError("Attempted to construct a Dataset with an empty list.")
        for row in rows.rows:
            if not isinstance(row, dict):
                raise ValueError(
                    "Attempted to construct a Dataset with a non-dict object. Found type: "
                    + str(type(row))
                    + " of row: "
                    + short_str(row)
                )
            if len(row) == 0:
                raise ValueError(
                    "Attempted to construct a Dataset row with an empty dict."
                )
        return rows
    
    def __iter__(self):
        return ((k, v) for k, v in self.rows.items())

    def __len__(self) -> int:
        return len(self.rows)

    def __str__(self) -> str:
        features = list(self.rows.rows[0].keys()) if self.rows.rows else []
        return f"Dataset({{\n    name: '{self.name}',\n    features: {features},\n    num_rows: {len(self.rows)}\n}})"


    @weave.op()
    async def map(self, model_or_func: Union[Callable, Model], *args, **kwargs) -> "Dataset":
            
        new_dataset_rows = []

        start_time = time.time()

        async def eval_example(row: dict) -> dict:
            if callable(model_or_func):
                fn = model_or_func
            else:
                fn = get_infer_method(model_or_func)
            try:
                map_results = await async_call(fn, **row)
            except OpCallError as e:
                raise e
            except Exception as e:
                print("Map failed")
                traceback.print_exc()
                return {}
            return map_results
        
        n_complete = 0
        _rows = list(self.rows)
        async for example, map_results in async_foreach(
            _rows, eval_example, get_weave_parallelism()
        ):
            n_complete += 1
            example.update({"map_results": map_results})
            new_dataset_rows.append(example)
        duration = time.time() - start_time
        print(f"Mapped {n_complete} of {len(_rows)} examples in {duration:.2f} seconds")
        return Dataset(name=self.name, rows=new_dataset_rows)
            

