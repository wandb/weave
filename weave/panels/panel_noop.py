import weave
from .. import panel


@weave.type()
class Noop(panel.Panel):
    id = "Noop"
