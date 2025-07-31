from weave.trace_server.external_to_internal_trace_server_adapter import (
    IdConverter,
    universal_int_to_ext_ref_converter,
)
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelArgs,
    EvaluateModelDispatcher,
    evaluate_model,
)


class EvaluateModelTestDispatcher(EvaluateModelDispatcher):
    def __init__(self, id_converter: IdConverter):
        self.id_converter = id_converter

    def dispatch(self, args: EvaluateModelArgs) -> None:
        externalized_args = universal_int_to_ext_ref_converter(
            args, self.id_converter.int_to_ext_project_id
        )
        evaluate_model(externalized_args)
