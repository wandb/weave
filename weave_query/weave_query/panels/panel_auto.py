import weave_query as weave

from weave_query.weave_query import panel


# Currently Auto is not a real panel, the system handles it.
@weave.type()
class Auto(panel.Panel):
    id = "Auto"
