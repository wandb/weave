import datetime
import itertools
import random
import threading
import time
import weave
from weave.timestamp import tz_aware_dt


@weave.type()
class Prediction:
    timestamp: datetime.datetime
    input: float
    output: float


@weave.type()
class EvalModel:
    id: str

    @weave.op(pure=False)
    def all_predictions(
        self, start_datetime: datetime.datetime, end_datetime: datetime.datetime
    ) -> list[Prediction]:
        pred_procs_node = weave.ops.objects(
            PredictionProcess.WeaveType(), "latest", 0  # type: ignore
        ).filter(lambda proc: proc.get().model.id == self.id)
        # TODO: this'll be slow! Should all be done in weave
        # TODO: use ref metadata to determine if a given obj falls
        #    in the window. (or lazily load refs and put metadata on PredProc)
        pred_procs = weave.use(pred_procs_node)
        res = list(itertools.chain(*(p.get().predictions for p in pred_procs)))
        return [
            p
            for p in res
            if p.timestamp > tz_aware_dt(start_datetime)
            and p.timestamp < tz_aware_dt(end_datetime)
        ]


@weave.type()
class PredictionProcess:
    id: int
    model: EvalModel
    predictions: list[Prediction]


class Predictor(threading.Thread):
    def __init__(self, model_id, run_for_s):
        threading.Thread.__init__(self)
        self.model = EvalModel(model_id)
        self.prediction_process = PredictionProcess(
            random.randrange(0, 10000000), self.model, []
        )
        self.run_for_s = run_for_s

    def run(self):
        start_time = time.time()
        while time.time() - start_time < self.run_for_s:
            for i in range(50):
                self.prediction_process.predictions.append(
                    Prediction(random.random(), random.random())
                )
                time.sleep(0.1)
            weave.save(
                self.prediction_process,
                name=f"model_preds-{self.model.id}-{self.prediction_process.id}",
            )


# Data model
# run.log()
