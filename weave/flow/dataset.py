from typing import Any, Iterable, Optional, Union

from pydantic import Field, field_validator

from weave.flow.obj import Object
from weave.flow.util import map_nested_dict
from weave.trace.op import Op
from weave.trace.table import Table
from weave.trace.weave_client import Call


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

    rows: Union[Table, Iterable[dict]] = Field(default_factory=lambda: Table(rows=[]))

    @field_validator("rows", mode="before")
    def convert_to_table(cls, rows: Any) -> Table:
        if rows is None:
            return Table(rows=[])

        if isinstance(rows, Table):
            return rows

        if isinstance(rows, Iterable):
            lst = []
            for row in rows:
                if not isinstance(row, dict):
                    raise ValueError(f"Expected dict, got {type(row)}")
                lst.append(row)
            return Table(rows=lst)

        raise ValueError(f"Cannot convert `{type(rows)}` to weave.Table")


def prep_for_dataset(
    call: Call, column_mapping: Optional[dict[str, str]] = None
) -> dict:
    d = call.to_dict()

    # TODO: hack to resolve op binding issue
    if "self" in d.get("inputs", {}):
        del d["inputs"]["self"]

    if column_mapping:
        d = map_nested_dict(d, column_mapping)

    return d


def add_calls_to_dataset(
    calls: list[Call],
    dataset: Optional[Dataset] = None,
    *,
    dataset_mapping: Optional[dict[str, str]] = None,
) -> Dataset:
    calls_as_dicts = [prep_for_dataset(c, dataset_mapping) for c in calls]

    if dataset is None:
        dataset = Dataset()

    if not dataset.rows:
        dataset = Dataset(rows=Table(rows=calls_as_dicts))
    else:
        dataset = Dataset(rows=Table(rows=dataset.rows.rows + calls_as_dicts))

    return dataset


def register_mapping(dataset: Dataset, op: Op, mapping: dict[str, str]) -> None: ...
