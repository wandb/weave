import importlib
import os
import sys
from pathlib import Path
from types import ModuleType

from fastapi import FastAPI

source_root = Path(os.environ["WEAVE_MIN_SERVER_SOURCE"])
weave_package = ModuleType("weave")
weave_package.__path__ = [str(source_root / "weave")]
sys.modules["weave"] = weave_package
tsi = importlib.import_module("weave.trace_server.trace_server_interface")

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/feedback/batch/create")
def feedback_create_batch(req: tsi.FeedbackCreateBatchReq) -> dict[str, list]:
    return {"res": []}
