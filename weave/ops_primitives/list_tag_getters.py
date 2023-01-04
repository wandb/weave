from .. import weave_types as types
from ..language_features.tagging import make_tag_getter_op

group_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "groupKey", types.Any(), op_name="group-groupkey"
)

index_checkpoint_tag_getter_op = make_tag_getter_op.make_tag_getter_op(
    "indexCheckpoint", types.Int(), op_name="tag-indexCheckpoint"
)

join_obj_getter_op = make_tag_getter_op.make_tag_getter_op(
    "joinObj", types.Any(), types.Any(), "tag-joinObj"
)
