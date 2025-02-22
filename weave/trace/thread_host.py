import uvicorn
from pydantic import BaseModel

import weave
from weave.trace.op import Op

# from typing import Generic, TypeVar

# STATE_T = TypeVar("STATE_T")
# INPUT_T = TypeVar("INPUT_T")
# OUTPUT_T = TypeVar("OUTPUT_T")

# class ThreadedModel(weave.Model, Generic[STATE_T, INPUT_T, OUTPUT_T]):
#     def fetch_thread_state(self, thread_id: str) -> STATE_T:
#         raise NotImplementedError("Subclasses must implement this method")

#     def store_thread_state(self, thread_id: str, thread_state: STATE_T, input: INPUT_T, output: OUTPUT_T):
#         raise NotImplementedError("Subclasses must implement this method")

#     @weave.op()
#     def predict(self, input: INPUT_T, thread_id: str) -> OUTPUT_T:
#         raise NotImplementedError("Subclasses must implement this method")

#     def predict_with_state():
#         ra

# class MyModel(ThreadedModel[int, int, int]):
#     def predict(self, input: int, thread_id: str) -> int:
#         return input + 1

class ThreadPredictRequest(BaseModel):
    thread_id: str

def host_op(
        req_type: type[ThreadPredictRequest],
        op: Op,
        port: int = 2323,
        allowed_origins: list[str] = [
            "https://app.wandb.test",
            "https://wandb.ai",
            "https://localhost:3000",
            "http://localhost:3000",  # Allow HTTP for local development
            "http://app.wandb.test",  # Allow HTTP for local development
        ],
):
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/thread/schema")
    async def thread_spec():
        return req_type.model_json_schema()

    # TODO: ProjectID should be configurable
    @app.post("/thread/run")
    async def thread(item: req_type):
        with weave.attributes(dict(thread_id=item.thread_id)):
            return await op(**item.model_dump())

    uvicorn.run(app, host="0.0.0.0", port=port)
