from datetime import datetime

from pydantic import BaseModel


class WeaveClientStatusState(BaseModel):
    moment: datetime
    future_exec_queue_size: int
    future_exec_worker_count: int
    call_processor_queue_size: int
    call_processor_worker_count: int
    remote_request_counter: dict[str, int]
