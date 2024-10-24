import weave
from weave.trace_server.interface.collections.action_collection import (
    ActionOpMapping,
    ActionWithConfig,
)


class ActionWithConfigObject(weave.Object, ActionWithConfig):
    pass


class ActionOpMappingObject(weave.Object, ActionOpMapping):
    pass
