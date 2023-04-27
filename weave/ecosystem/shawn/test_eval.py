import datetime
import weave
from . import eval
from weave.timestamp import tz_aware_dt


def test_data():
    model = eval.EvalModel("a")

    proc = eval.PredictionProcess("000", model, [])
    pred1 = eval.Prediction(datetime.datetime(2022, 10, 8, 10, 26), 0, 3)
    proc.predictions.append(pred1)
    pred2 = eval.Prediction(datetime.datetime(2022, 10, 8, 10, 31), 1, 4)
    proc.predictions.append(pred2)
    weave.save(proc, name="proc-a:latest")

    proc = eval.PredictionProcess("000", model, [])
    pred3 = eval.Prediction(datetime.datetime(2022, 10, 8, 10, 39), 9, 10)
    proc.predictions.append(pred3)
    weave.save(proc, name="proc-b:latest")

    res = weave.use(
        model.all_predictions(
            datetime.datetime(2022, 10, 8, 10, 30),
            datetime.datetime(2022, 10, 8, 10, 40),
        )
    )

    # The weave system will always return tz-aware datetimes, so we need to
    # convert the expected values to be tz-aware as well.
    pred2.timestamp = tz_aware_dt(pred2.timestamp)
    pred3.timestamp = tz_aware_dt(pred3.timestamp)
    assert res == [pred2, pred3]
