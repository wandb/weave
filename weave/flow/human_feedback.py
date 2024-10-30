from typing import Optional

from weave.flow.obj import Object


class HumanAnnotationColumn(Object):
    json_schema: dict

    # If true, all unique creators will have their
    # own value for this feedback type. Otherwise,
    # by default, the value is shared and can be edited.
    unique_among_creators: bool = False

    # If provided, this feedback type will only be shown
    # when a call is generated from the given op
    op_scope: Optional[list[str]] = None
