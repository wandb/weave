import weave_query as weave
import weave_query
from weave_query import panel

# TODO: This id conflicts with the histogram type! Panel types
# should automatically have Panel in the name but they don't at the moment.


@weave.type("histogram")
class Histogram(panel.Panel):
    id = "histogram"
