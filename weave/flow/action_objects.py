import weave
from weave.trace_server.interface.actions import ActionOpMapping, ActionWithConfig


class ActionWithConfigObject(ActionWithConfig, weave.Object):
    pass


class ActionOpMappingObject(ActionOpMapping, weave.Object):
    pass
