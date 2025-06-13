from weave.trace_server.interface.evaluations.model_class import TSEIMModelClassMixin
from weave.trace_server.interface.evaluations.model_instance import (
    TSEIMModelInstanceMixin,
)


class TraceServerEvaluationInterfaceMixin(
    TSEIMModelClassMixin, TSEIMModelInstanceMixin
): ...
