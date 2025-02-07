
from typing import Any

import uuid_utils as uuid

import weave
from weave.trace.context.weave_client_context import require_weave_client
from weave.trace.refs import TableRef
from weave.trace.vals import make_trace_obj
from weave.trace_server.trace_server_interface import (
    TableCreateReq,
    TableSchemaForInsert,
    TableUpdateReq,
)


@contextmanager
def parent_call(trace_id: str, parent_call_id: str):
    if os.environ.get("DISABLE_PARENT_CALL"):
        yield
    else:
        with set_call_stack([Call(
                trace_id=trace_id,
                id=parent_call_id,
                # These values are sadly required, but can be ignored
                _op_name="", # can be ignored
                project_id="", # can be ignored
                parent_id=None, # can be ignored
                inputs={} # can be ignored
        )]):
            yield

class SyntheticModel(weave.Model):
    model_id: str
    _output_val: Any

    @weave.op
    def predict(self, input: Any) -> Any:
        return self._output_val


class EvalPredictionRecord:
    def __init__(self, input: Any, output: Any):
        self._input = input
        self._output = output

    def record_score(self, key: str, value: Any):
        pass



class EvalLogger:
    def __init__(self):
        # These IDs are critical to define up front so we can delay making the parent until
        # the end of the evaluation.
        self._evaluation_call_id = str(uuid.uuid7())
        self._evaluation_trace_id = str(uuid.uuid7())
        self._weave_table_digest = None
        self._dataset_name = "eval_logger_dataset" # Make a param!
        self._model = SyntheticModel(model_id = str(uuid.uuid7()))

    def _add_row_to_dataset(self, row: dict):
        if self._weave_table_digest is None:
            client = require_weave_client()
            res = client.server.table_create(TableCreateReq(
                table = TableSchemaForInsert(
                    project_id = client._project_id(),
                    rows = [row]
                )
            ))
            self._weave_table_digest = res.digest
        else:
            client = require_weave_client()
            res = client.server.table_update(TableUpdateReq(
                project_id = client._project_id(),
                base_digest = self._weave_table_digest,
                updates = [{
                    "append": {
                        "row": row
                    }
                }]
            ))


    def record_prediction(self, input, output) -> EvalPredictionRecord:
        self._add_row_to_dataset({
            "input": input,
        })
        woth

    def record_summary(self, summary: dict):
        client = require_weave_client()
        self._dataset = weave.Dataset(name = self._dataset_name, rows = make_trace_obj(
                val=TableRef(
                    entity = client.entity,
                    project = client.project,
                    _digest = self._weave_table_digest,
                ),
                new_ref=None,
                server=client.server,
                root=None,
                parent=None
            ))
        evaluation = weave.Evaluation(dataset=self._dataset, scorers=[])
        weave.publish(evaluation)
