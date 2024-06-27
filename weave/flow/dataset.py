import inspect
from typing import Any, Callable, Union
import time
import traceback
import textwrap
import asyncio


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
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __str__(self) -> str:
        features = list(self.rows.rows[0].keys()) if self.rows.rows else []
        result = f"Dataset({{\n"
        if self.name:
            result += f"    name: '{self.name}',\n"
        if self.description:
            result += f"    description: '{self.description}',\n"
        result += f"    features: {features},\n    num_rows: {len(self.rows)}\n}}"
        return result


    @weave.op()
    def map(self, model_or_func: Union[Callable, Model], *args, **kwargs) -> "Dataset":
        async def async_map():
            new_dataset_rows = []
            start_time = time.time()

            async def eval_example(row: dict) -> dict:
                if callable(model_or_func):
                    fn = model_or_func
                else:
                    fn = get_infer_method(model_or_func)
                
                fn_signature = inspect.signature(fn)
                fn_arg_names = list(fn_signature.parameters.keys())
                
                fn_args = {k: v for k, v in row.items() if k in fn_arg_names}
                
                if not fn_args:
                    raise ValueError(f"Function {fn.__name__} expects arguments: {fn_arg_names}, but none of these match the keys in the row: {list(row.keys())}")
                
                try:
                    map_results = await async_call(fn, **fn_args)
                except OpCallError as e:
                    raise e
                except Exception as e:
                    print("Map failed")
                    traceback.print_exc()
                    return {}
                if isinstance(map_results, dict):
                    return map_results
                else:
                    message = textwrap.dedent(
                        f"""
                        Call error:

                        The returning value of the function ({model_or_func.__name__}) you are trying to map  must be a dictionary.
                        """
                    )
                    raise OpCallError(message)
            
            n_complete = 0
            _rows = list(self.rows)
            async for example, map_results in async_foreach(
                _rows, eval_example, get_weave_parallelism()
            ):
                n_complete += 1
                example.update(map_results)
                new_dataset_rows.append(example)
            duration = time.time() - start_time
            print(f"Mapped {n_complete} of {len(_rows)} examples in {duration:.2f} seconds")
            return Dataset(name=self.name, rows=new_dataset_rows)

        return asyncio.get_event_loop().run_until_complete(async_map())
