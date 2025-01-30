from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any

from pydantic import field_validator
from typing_extensions import Self

import weave
from weave.flow.obj import Object
from weave.trace.objectify import register_object
from weave.trace.vals import WeaveObject, WeaveTable
from weave.trace.weave_client import Call

if TYPE_CHECKING:
    import pandas as pd


def short_str(obj: Any, limit: int = 25) -> str:
    str_val = str(obj)
    if len(str_val) > limit:
        return str_val[:limit] + "..."
    return str_val


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

    rows: weave.Table

    @classmethod
    def from_obj(cls, obj: WeaveObject) -> Self:
        return cls(
            name=obj.name,
            description=obj.description,
            ref=obj.ref,
            rows=obj.rows,
        )

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

    @field_validator("rows", mode="before")
    def convert_to_table(cls, rows: Any) -> weave.Table:
        if not isinstance(rows, weave.Table):
            table_ref = getattr(rows, "table_ref", None)
            if isinstance(rows, WeaveTable):
                rows = list(rows)
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
        # TODO: This can be slow for large datasets...
        return len(list(self.rows))

    def __getitem__(self, key: int) -> dict:
        if key < 0:
            raise IndexError("Negative indexing is not supported")
        return self.rows[key]

    def get_column(self, name: str) -> list[Any]:
        """Get all values for a column in the dataset.

        This method may be slow since we have to materialize all of the rows of the dataset.
        """
        try:
            return [row[name] for row in self.rows]
        except KeyError:
            raise KeyError(f"Column {name} not found in dataset")
