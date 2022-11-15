import datetime
import weave
from . import eval


def test_data():
    model = eval.Model("a")

    proc = eval.PredictionProcess("000", model, [])
    pred1 = eval.Prediction(datetime.datetime(2022, 10, 8, 10, 26), 0, 3)
    proc.predictions.append(pred1)
    pred2 = eval.Prediction(datetime.datetime(2022, 10, 8, 10, 31), 1, 4)
    proc.predictions.append(pred2)
    weave.save(proc, name="proc-a")

    proc = eval.PredictionProcess("000", model, [])
    pred3 = eval.Prediction(datetime.datetime(2022, 10, 8, 10, 39), 9, 10)
    proc.predictions.append(pred3)
    weave.save(proc, name="proc-b")

    res = weave.use(
        model.all_predictions(
            datetime.datetime(2022, 10, 8, 10, 30),
            datetime.datetime(2022, 10, 8, 10, 40),
        )
    )
    assert res == [pred2, pred3]
