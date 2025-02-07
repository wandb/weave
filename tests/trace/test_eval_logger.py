import weave
from weave.flow.eval_logger import EvalLogger


def test_eval_logger():
    weave.init("test_eval_logger")
    logger = EvalLogger()
    for i in range(10):
        logger.record_prediction(f"test_input_{i}", f"test_output_{i}")
    logger.record_summary({"sum_key": "sum_val"})
    assert False
