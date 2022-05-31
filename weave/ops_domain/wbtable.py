from wandb.apis import public as wandb_api
from wandb import data_types as wandb_data_types

from ..api import op, weave_class
from .. import weave_types as types


class TableType(types.Type):
    name = "table"
    instance_classes = wandb_data_types.Table
    instance_class = wandb_data_types.Table


@weave_class(weave_type=TableType)
class Table:
    @op(name="table-rowsType", output_type=types.Type())
    def rows_type(table: wandb_data_types.Table):
        print("TABLE ROWS TYPE SELF", table)
        # TODO: not done. But I'm going to switch to working on
        #     using media in the new system to see how that feels.
