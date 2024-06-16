import weave
from weave.old_weave import panel


# Currently Auto is not a real panel, the system handles it.
@weave.type()
class Auto(panel.Panel):
    id = "Auto"
