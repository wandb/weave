from weave.trace_server.interface.evaluations.ExampleLabel import (
    TSEIMExampleLabelMixin,
)
from weave.trace_server.interface.evaluations.GenerationResult import (
    TSEIMGenerationResultMixin,
)
from weave.trace_server.interface.evaluations.InputPayload import TSEIMInputPayloadMixin
from weave.trace_server.interface.evaluations.ModelClass import TSEIMModelClassMixin
from weave.trace_server.interface.evaluations.ModelInstance import (
    TSEIMModelInstanceMixin,
)
from weave.trace_server.interface.evaluations.ScorerClass import TSEIMScorerClassMixin
from weave.trace_server.interface.evaluations.ScoreResult import TSEIMScoreResultMixin
from weave.trace_server.interface.evaluations.ScorerInstance import (
    TSEIMScorerInstanceMixin,
)
from weave.trace_server.interface.evaluations.TaskDefinition import (
    TSEIMTaskDefinitionMixin,
)
from weave.trace_server.interface.evaluations.TaskExample import (
    TSEIMTaskExampleMixin,
)


class TraceServerEvaluationInterfaceMixin(
    TSEIMModelClassMixin,
    TSEIMModelInstanceMixin,
    TSEIMInputPayloadMixin,
    TSEIMGenerationResultMixin,
    TSEIMTaskDefinitionMixin,
    TSEIMTaskExampleMixin,
    TSEIMScorerClassMixin,
    TSEIMScorerInstanceMixin,
    TSEIMScoreResultMixin,
    TSEIMExampleLabelMixin,
): ...
