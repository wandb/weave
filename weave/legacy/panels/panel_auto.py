import weave
from weave.legacy import panel


# Currently Auto is not a real panel, the system handles it.
@weave.type()
class Auto(panel.Panel):
    id = "Auto"
