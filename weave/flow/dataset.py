import copy
import inspect
import traceback
import warnings
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
from weave.flow.util import IterationSpeedColumn, async_foreach, short_str, wrap_lambda
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.env import get_weave_parallelism
from weave.trace.isinstance import weave_isinstance
from weave.trace.objectify import register_object
from weave.trace.op_caller import async_call
from weave.trace.vals import WeaveObject, WeaveTable
from weave.trace.weave_client import (
    Call,
)

console = Console()

if TYPE_CHECKING:
    import pandas as pd

    # Import huggingface datasets for type checking
    from datasets import Dataset as HFDataset
    from datasets import DatasetDict as HFDatasetDict


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

    @classmethod
    def from_hf(cls, hf_dataset: Union["HFDataset", "HFDatasetDict"]) -> Self:
        try:
            from datasets import Dataset as HFDataset
            from datasets import DatasetDict as HFDatasetDict
        except ImportError:
            raise ImportError(
                "huggingface datasets is required to use this method. "
                "Install with `pip install datasets`"
            ) from None

        if isinstance(hf_dataset, HFDatasetDict):
            if "train" in hf_dataset:
                warnings.warn(
                    "Input dataset has multiple splits. Using 'train' split by default.",
                    stacklevel=2,
                )
                target_hf_dataset = hf_dataset["train"]
            else:
                raise ValueError(
                    "Input is a DatasetDict but does not contain a 'train' split. "
                    "Please provide a specific split (e.g., dataset_dict['test']) "
                    "or a datasets.Dataset object."
                )
        elif isinstance(hf_dataset, HFDataset):
            target_hf_dataset = hf_dataset
        else:
            raise TypeError(
                "Expected a datasets.Dataset or datasets.DatasetDict object, "
                f"got {type(hf_dataset)}"
            )

        # Convert HF Dataset to list of dicts
        rows = target_hf_dataset.to_list()
        return cls(rows=rows)

    def to_pandas(self) -> "pd.DataFrame":
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required to use this method") from None

        return pd.DataFrame(self.rows)

    def to_hf(self) -> "HFDataset":
        try:
            from datasets import Dataset as HFDataset
        except ImportError:
            raise ImportError(
                "huggingface datasets is required to use this method. "
                "Install with `pip install datasets`"
            ) from None
        # Convert list of dicts to HF Dataset format (dict of lists)
        if not self.rows:
            return HFDataset.from_dict({})
        data = {key: [row.get(key) for row in self.rows] for key in self.rows[0]}
        return HFDataset.from_dict(data)

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
    def convert_to_table(cls, rows: Any) -> Union[weave.Table, WeaveTable]:  # noqa: N805
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

    @weave.op
    async def map(
        self, func: Callable, num_procs: int = get_weave_parallelism()
    ) -> "Dataset":
        """
        Apply a function to each row of the dataset in parallel and return a new dataset.

        The `map` method transforms each row in the dataset by applying `func` to it, adding or
        updating columns based on the dictionary returned by the function. This is the primary
        way to transform or enrich datasets.

        Parameter Mapping:
            The function parameters are automatically matched with dataset columns by name.
            For example, if `func` has parameters `(id, text)` and the dataset has columns
            `id`, `text`, and `timestamp`, the function will be called with only the `id` and
            `text` values for each row.

        Dictionary Return Requirement:
            Functions MUST return a dictionary mapping column names to values. Each key-value
            pair in the returned dictionary will be added to or update the corresponding row.
            Returning non-dictionary types (such as integers, strings, lists) will raise a TypeError.

        Parallelism:
            Processing happens in parallel across multiple processors, controlled by `num_procs`.
            A rich progress bar is displayed during processing.

        Immutability:
            The original dataset remains unchanged. A new Dataset instance is returned with
            the transformed rows.

        Args:
            func: A function that takes specific columns as parameters and returns a dictionary
                 mapping new or updated column names to values. The function can be synchronous
                 or asynchronous and can include type annotations.

            num_procs: The number of parallel processes to use. Defaults to the value set by
                     the `WEAVE_PARALLELISM` environment variable.

        Returns:
            A new `Dataset` object containing the processed rows with updates applied.

        Raises:
            TypeError: If the function does not return a dictionary.
            ValueError: If the function requires parameters not present in the dataset.
            Exception: Any exception raised by the function during processing is propagated.

        Examples:
            ```python
            import weave

            # Create a dataset
            ds = weave.Dataset(rows=[
                {"id": 1, "text": "Hello world", "lang": "en"},
                {"id": 2, "text": "Bonjour monde", "lang": "fr"},
                {"id": 3, "text": "Hola mundo", "lang": "es"}
            ])

            # Example 1: Simple transformation with a single parameter
            def add_text_length(text):
                return {"length": len(text)}

            # Example 2: Multi-parameter function with type hints
            def combine_fields(id: int, text: str, lang: str) -> dict:
                return {
                    "display": f"[{id}] {text} ({lang})",
                    "uppercase": text.upper()
                }

            # Example 3: Function with default parameters
            def classify_language(lang, default_category="other"):
                categories = {"en": "english", "es": "spanish", "fr": "french"}
                return {"category": categories.get(lang, default_category)}

            # Apply the transformations
            ds_with_length = ds.map(add_text_length)
            ds_combined = ds.map(combine_fields)
            ds_categorized = ds.map(classify_language)

            # Example output for ds_with_length[0]:
            # {
            #     "id": 1,
            #     "text": "Hello world",
            #     "lang": "en",
            #     "length": 11
            # }
            ```
        """
        processed_rows: list[tuple[int, dict]] = []

        # Inspect the function signature
        sig = inspect.signature(func)
        param_names = list(sig.parameters.keys())

        # Convert lambda to named function for better async handling
        func = wrap_lambda(func)

        # Store the function name before applying weave.op
        func_name = getattr(func, "__name__", "unknown_function")

        # Apply weave.op after lambda conversion
        func = weave.op(func)

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
                # asyncify the function call
                result = await async_call(func, **kwargs)

                # Handle the result based on its type
                if not isinstance(result, dict):
                    # Raise error for non-dictionary returns
                    raise TypeError(
                        f"Function must return a dictionary, but got {type(result).__name__} "
                        f"from function '{func_name}'. Use a dictionary to specify "
                        f"which columns to add or update."
                    )
            except Exception as e:
                # Log the error and propagate it to stop the map operation
                print(f"Error processing row with map function: {short_str(row)}")
                traceback.print_exc()
                raise e
            else:
                row_copy = copy.deepcopy(row)
                row_copy.update(result)
                return row_copy

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
            # Return the coroutine so the caller can await it
            async for index, _, processed_row in async_foreach(
                self.rows,
                process_row,
                num_procs,
                progress=progress,
                progress_desc="Mapping dataset",
            ):
                processed_rows.append((index, processed_row))

        # Sort by index to maintain original order
        processed_rows.sort(key=lambda x: x[0])
        final_rows = [processed_row for _, processed_row in processed_rows]

        return self.__class__(rows=final_rows)
