from weave.trace_server.workers.evaluate_model_worker.evaluate_model_worker import (
    EvaluateModelArgs,
    EvaluateModelDispatcher,
)


class EvaluationModelDispatcherTestAdapter(EvaluateModelDispatcher):
    def dispatch(self, args: EvaluateModelArgs) -> None:
        raise NotImplementedError("Not implemented")
