# Load a model from an artifact, and then server, logging the results to a streamtable

import os
from contextlib import asynccontextmanager

from pydantic import BaseModel
from fastapi import FastAPI
import weave


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    global stream_table

    model = weave.ref(os.environ["MODEL_REF"]).get()
    weave.init(os.environ["PROJECT_NAME"])

    yield


app = FastAPI(lifespan=lifespan)


class Item(BaseModel):
    example: str


@app.post("/predict")
def predict(item: Item):
    result = model.predict(item.example)
    return {"prediction": result}
