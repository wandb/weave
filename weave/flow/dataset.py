from collections.abc import Iterable, Iterator
from functools import cached_property
from typing import TYPE_CHECKING, Any, Union

from pydantic import field_validator
from typing_extensions import Self

import weave
from weave.flow.obj import Object
from weave.flow.util import short_str
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.isinstance import weave_isinstance
from weave.trace.objectify import register_object
from weave.trace.vals import WeaveObject, WeaveTable
from weave.trace.weave_client import (
    Call,
)

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
