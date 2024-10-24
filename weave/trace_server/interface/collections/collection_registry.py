from weave.trace_server.interface.collections.action_collection import (
    action_op_mapping_collection,
    action_with_config_collection,
)
from weave.trace_server.interface.collections.collection import Collection

collections: list[Collection] = [
    action_with_config_collection,
    action_op_mapping_collection,
]
