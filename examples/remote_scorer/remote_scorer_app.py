"""FastAPI reference adapter for a Weave remote scorer endpoint."""

from __future__ import annotations

import logging
import os
from typing import Any

import uvicorn
from auth import validate_bearer_token
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from scoring_logic import REMOTE_SCORER_SCHEMA_VERSION, score_remote_call

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="Weave remote scorer sample", version="1.0.0")
security = HTTPBearer(auto_error=False)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/score")
async def score(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
) -> dict[str, Any]:
    correlation_id = request.headers.get("X-Correlation-ID")
    idempotency_key = request.headers.get("Idempotency-Key")
    schema_version = request.headers.get("X-Weave-Schema-Version")

    if credentials is None or not validate_bearer_token(credentials.credentials):
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
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
    )
