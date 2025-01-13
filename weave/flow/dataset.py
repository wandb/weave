from collections.abc import Iterator
from typing import Any, Union, overload

from pydantic import field_validator

import weave
from weave.flow.obj import Object
from weave.trace.vals import WeaveTable


def short_str(obj: Any, limit: int = 25) -> str:
    str_val = str(obj)
    if len(str_val) > limit:
        return str_val[:limit] + "..."
    return str_val


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

    @overload
    def __getitem__(self, key: int) -> dict: ...
    @overload
    def __getitem__(self, key: slice) -> list[dict]: ...
    def __getitem__(self, key: Union[int, slice]) -> Union[dict, list[dict]]:
        if isinstance(key, int):
            if key < 0:
                raise IndexError("Negative indexing is not supported")
            return self.rows[key]
        elif isinstance(key, slice):
            if key.start is not None and key.start < 0:
                raise IndexError("Negative indexing is not supported")
            if key.stop is not None and key.stop < 0:
                raise IndexError("Negative indexing is not supported")
            if key.step is not None and key.step < 0:
                raise IndexError("Negative step is not supported")
            return list(self.rows[key])

        raise TypeError(f"Invalid key type: {type(key)}")
