from weave.trace_server.external_to_internal_trace_server_adapter import (
    IdConverter,
    universal_int_to_ext_ref_converter,
)
from weave.trace_server.trace_server_interface import (
    EvaluateModelArgs,
    EvalWorkerJob,
    RescoringArgs,
)
from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelDispatcher,
    evaluate_model,
)
from weave.trace_server.workers.evaluate_model_worker.rescore_worker import (
    rescore_predictions_sync,
)


class EvaluateModelTestDispatcher(EvaluateModelDispatcher):
    def __init__(self, id_converter: IdConverter):
        self.id_converter = id_converter

    def dispatch(self, args: EvalWorkerJob) -> None:
        externalized_args = universal_int_to_ext_ref_converter(
            args, self.id_converter.int_to_ext_project_id
        )
        if isinstance(externalized_args, RescoringArgs):
            rescore_predictions_sync(externalized_args)
        elif isinstance(externalized_args, EvaluateModelArgs):
            evaluate_model(externalized_args)
        else:
            raise TypeError(
                f"Unknown job type: {type(externalized_args).__name__}. "
                "Update EvaluateModelTestDispatcher to handle new job types."
            )
