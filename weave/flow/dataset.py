import asyncio
import inspect  # Added for function signature inspection
import traceback
from collections.abc import Iterable, Iterator
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Union

from pydantic import field_validator
from rich.console import Console  # Added Console import

# from weave.flow.eval import console # REMOVED due to circular import
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from typing_extensions import Self

import weave
from weave.flow.obj import Object
from weave.flow.util import IterationSpeedColumn, async_foreach, short_str
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.env import get_weave_parallelism
from weave.trace.isinstance import weave_isinstance
from weave.trace.objectify import register_object
from weave.trace.vals import WeaveObject, WeaveTable
from weave.trace.weave_client import (
    Call,
)

console = Console()

if TYPE_CHECKING:
    import pandas as pd


@register_object
class Dataset(Object):
    """
    Dataset object with easy saving and automatic versioning

    Examples:

    ```python
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

    rows: Union[weave.Table, WeaveTable]

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        field_values = {}
        for field_name in cls.model_fields:
            if hasattr(obj, field_name):
                field_values[field_name] = getattr(obj, field_name)

        return cls(**field_values)

    @classmethod
    def from_calls(cls, calls: Iterable[Call]) -> Self:
        rows = [call.to_dict() for call in calls]
        return cls(rows=rows)

    @classmethod
    def from_pandas(cls, df: "pd.DataFrame") -> Self:
        rows = df.to_dict(orient="records")
        return cls(rows=rows)

    def to_pandas(self) -> "pd.DataFrame":
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to use this method")

        return pd.DataFrame(self.rows)

    def add_rows(self, rows: Iterable[dict]) -> "Dataset":
        """Create a new dataset version by appending rows to the existing dataset.

        This is useful for adding examples to large datasets without having to
        load the entire dataset into memory.

        Args:
            rows: The rows to add to the dataset.

        Returns:
            The updated dataset.
        """
        client = require_weave_client()
        if not isinstance(self.rows, WeaveTable) or not self.rows.table_ref:
            raise TypeError(
                "This dataset is not saved to weave. Call weave.publish(dataset) "
                "to save the dataset before adding rows."
            )
        if self.rows.table_ref.project != client.project:
            raise ValueError(
                "This dataset is not saved to the same project as the current weave client. "
                "Client is in project:  "
                + client.project
                + " but dataset is in project: "
                + self.rows.table_ref.project
            )
        if self.rows.table_ref.entity != client.entity:
            raise ValueError(
                "This dataset is not saved to the same entity as the current weave client. "
                "Client is in entity: "
                + client.entity
                + " but dataset is in entity: "
                + self.rows.table_ref.entity
            )

        new_table = client._append_to_table(self.rows.table_ref.digest, list(rows))
        new_dataset = Dataset(
            name=self.name, description=self.description, rows=new_table
        )
        weave.publish(new_dataset, name=self.name)
        return new_dataset

    @field_validator("rows", mode="before")
    def convert_to_table(cls, rows: Any) -> Union[weave.Table, WeaveTable]:
        if weave_isinstance(rows, WeaveTable):
            return rows
        if not isinstance(rows, weave.Table):
            table_ref = getattr(rows, "table_ref", None)
            rows = weave.Table(rows)
            if table_ref:
                rows.table_ref = table_ref
        if len(rows.rows) == 0:
            raise ValueError("Attempted to construct a Dataset with an empty list.")
        for row in rows.rows:
            if not isinstance(row, dict):
                raise TypeError(
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

    def __iter__(self) -> Iterator[dict]:
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, key: int) -> dict:
        if key < 0:
            raise IndexError("Negative indexing is not supported")
        return self.rows[key]

    def __str__(self) -> str:
        return f"Dataset({{\n    features: {list(self.columns_names)},\n    num_rows: {self.num_rows}\n}})"

    @cached_property
    def columns_names(self) -> list[str]:
        return list(self.rows[0].keys())

    @cached_property
    def num_rows(self) -> int:
        return len(self.rows)

    def select(self, indices: Iterable[int]) -> Self:
        """
        Select rows from the dataset based on the provided indices.

        Args:
            indices: An iterable of integer indices specifying which rows to select.

        Returns:
            A new Dataset object containing only the selected rows.
        """
        # Ensure indices is not empty before proceeding
        indices_list = list(indices)
        if not indices_list:
            raise ValueError("Cannot select rows with an empty set of indices.")

        selected_rows = [self[i] for i in indices_list]
        return self.__class__(rows=selected_rows)

    def map(self, func: Callable, num_procs: int = get_weave_parallelism()) -> Self:
        """
        Apply a function to each row of the dataset in parallel and return a new dataset.

        This method processes each row of the dataset by applying the provided function `func`
        to specific columns. The function can:

        1. Accept specific parameters matching column names in the dataset (`func(id, val)`)
        2. Return a dictionary of new/updated values
        3. Return a single value (which will be stored using the function name as key)

        The returned values will be used to update the original row's dictionary,
        effectively adding new columns or modifying existing ones.

        The processing happens in parallel using `asyncio` and `util.async_foreach`,
        controlled by the `num_procs` parameter. A progress bar will be displayed
        during processing.

        The original dataset remains unchanged (immutability).

        Args:
            func: A function (synchronous or asynchronous) that takes specific columns
                  as parameters, and returns updates for that row.
            num_procs: The number of parallel processes to use. Defaults to the value
                     set by the `WEAVE_PARALLELISM` environment variable or a sensible default.

        Returns:
            A new `Dataset` object containing the processed rows with the updates applied.

        Raises:
            TypeError: If the function `func` does not return a dictionary or a value.
            ValueError: If the function requires parameters not present in the dataset.
            Exception: Propagates any exception raised by `func` during processing of a row.

        Example:
            ```python
            import weave

            # Create a sample dataset
            ds = weave.Dataset(rows=[
                {"id": 1, "value": 10},
                {"id": 2, "value": 20}
            ])

            # Function with specific parameters
            def double_value(value):
                return {"value_doubled": value * 2}

            # Function returning a scalar value
            def sum_fields(id, value):
                return id + value  # Will be stored under key "sum_fields"

            # Apply the functions using map
            new_ds1 = ds.map(double_value)
            new_ds2 = ds.map(sum_fields)

            # Print the results
            print(new_ds1[0])  # {'id': 1, 'value': 10, 'value_doubled': 20}
            print(new_ds2[0])  # {'id': 1, 'value': 10, 'sum_fields': 11}
            ```
        """
        processed_rows = []

        # Inspect the function signature
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        async def process_row(row: dict) -> dict:
            try:
                # Extract and pass specific parameters
                kwargs = {}
                for name in param_names:
                    if name in row:
                        kwargs[name] = row[name]
                    else:
                        # Skip this parameter or use a default if available
                        if sig.parameters[name].default is not inspect.Parameter.empty:
                            kwargs[name] = sig.parameters[name].default
                        else:
                            raise ValueError(
                                f"Function expects parameter '{name}' but this column "
                                f"is not in the dataset row: {short_str(row)}"
                            )

                result = func(**kwargs)

                # If the user function is async, await it
                if asyncio.iscoroutine(result):
                    result = await result

                # Handle the result based on its type
                if not isinstance(result, dict):
                    # For non-dictionary returns, use the function name as the key
                    # If it's a lambda function, use "<lambda>" as key
                    fn_name = func.__name__
                    if fn_name == "<lambda>":
                        fn_name = "<lambda>"
                    result = {fn_name: result}
            except Exception as e:
                # Log the error and propagate it to stop the map operation
                print(f"Error processing row with map function: {short_str(row)}")
                traceback.print_exc()
                raise e
            else:
                # Update the original row with the results
                row_copy = row.copy()
                row_copy.update(result)
                return row_copy

        async def main(progress: Progress) -> Self:
            async for _, processed_row in async_foreach(
                self.rows,
                process_row,
                num_procs,
                progress=progress,
                progress_desc="Mapping dataset",
            ):
                processed_rows.append(processed_row)

            return self.__class__(rows=processed_rows)

        # Setup and run the progress bar and async processing
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            BarColumn(),
            IterationSpeedColumn(),
            TimeElapsedColumn(),
            console=console,  # Use the instantiated console
            transient=True,  # Remove progress bar when done
        ) as progress:
            return asyncio.run(main(progress))
