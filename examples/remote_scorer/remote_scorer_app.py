"""FastAPI reference adapter for a Weave remote scorer endpoint."""

from __future__ import annotations

import logging
import os
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request

from auth import extract_bearer_token, validate_bearer_token
from scoring_logic import REMOTE_SCORER_SCHEMA_VERSION, score_remote_call

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Weave remote scorer sample", version="1.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/score")
async def score(request: Request) -> dict[str, Any]:
    correlation_id = request.headers.get("X-Correlation-ID")
    idempotency_key = request.headers.get("Idempotency-Key")
    schema_version = request.headers.get("X-Weave-Schema-Version")

    token = extract_bearer_token(request.headers.get("Authorization"))
    if token is None or not validate_bearer_token(token):
        logger.warning(
            "unauthorized remote scorer request correlation_id=%s",
            correlation_id,
        )
        raise HTTPException(status_code=401, detail="unauthorized")

    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc

    logger.info(
        "received remote scorer request correlation_id=%s idempotency_key=%s schema_version=%s",
        correlation_id,
        idempotency_key,
        schema_version,
    )

    try:
        result = score_remote_call(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "schema_version": REMOTE_SCORER_SCHEMA_VERSION,
        "result": result,
    }


if __name__ == "__main__":
    uvicorn.run(
        "remote_scorer_app:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
