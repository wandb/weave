from typing import Optional

from weave.trace_server.interface.base_object_classes import base_object_def


class HumanAnnotationColumn(base_object_def.BaseObject):
    json_schema: dict

    # If true, all unique creators will have their
    # own value for this feedback type. Otherwise,
    # by default, the value is shared and can be edited.
    unique_among_creators: bool = False

    # If provided, this feedback type will only be shown
    # when a call is generated from the given op
    op_scope: Optional[list[str]] = None
