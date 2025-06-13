from weave.trace_server.interface.evaluations.GenerationResult import (
    TSEIMGenerationResultMixin,
)
from weave.trace_server.interface.evaluations.InputPayload import TSEIMInputPayloadMixin
from weave.trace_server.interface.evaluations.ModelClass import TSEIMModelClassMixin
from weave.trace_server.interface.evaluations.ModelInstance import (
    TSEIMModelInstanceMixin,
)
from weave.trace_server.interface.evaluations.TaskDescription import (
    TSEIMTaskDescriptionMixin,
)


class TraceServerEvaluationInterfaceMixin(
    TSEIMModelClassMixin,
    TSEIMModelInstanceMixin,
    TSEIMInputPayloadMixin,
    TSEIMGenerationResultMixin,
    TSEIMTaskDescriptionMixin,
): ...
