"""Object-key layout + presigned-URL minter for the export bucket.

Distinct from `weave.trace_server.file_storage`: that module handles
trace `files` blobs; this one is scoped to bulk-export artifacts whose
credentials come from the gorilla resolver per export.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

import boto3
from botocore.client import Config

from weave.trace_server.byob.resolver import ResolvedExportTarget
from weave.trace_server.export.constants import (
    EXPORT_OBJECT_NAME,
    EXPORT_PREFIX,
    SIGNED_URL_TTL,
)

logger = logging.getLogger(__name__)


def build_object_key(env: str, project_id: str, job_id: UUID) -> str:
    """`<env>/exports/<project_id>/<job_id>/data.parquet`."""
    return f"{env}/{EXPORT_PREFIX}/{project_id}/{job_id.hex}/{EXPORT_OBJECT_NAME}"


def build_dest_url(
    target: ResolvedExportTarget, env: str, project_id: str, job_id: UUID
) -> str:
    """Full `s3://bucket/<env>/exports/<project_id>/<job_id>/data.parquet`.

    Used as the `url = '<...>'` value inside the CREATE NAMED COLLECTION body;
    must validate against `URL_VALUE_REGEX` upstream of interpolation.
    """
    base = target.bucket_uri.rstrip("/")
    key = build_object_key(env, project_id, job_id)
    return f"{base}/{key}"


class PresignedUrlMinter:
    """Per-export presigned-URL minter.

    Constructed fresh per GET request: the credentials change per resolve,
    and there is no value in pooling boto3 clients here in v1 (the GET path
    is single-call). Phase 2 multi-part can revisit if mint volume warrants.
    """

    def __init__(self, target: ResolvedExportTarget, env: str) -> None:
        self._env = env
        self._target = target
        creds = target.credentials
        config = Config(signature_version="s3v4", retries={"max_attempts": 0})
        self._client = boto3.client(
            "s3",
            aws_access_key_id=creds.access_key_id,
            aws_secret_access_key=creds.secret_access_key.get_secret_value(),
            aws_session_token=creds.session_token.get_secret_value(),
            region_name=target.region,
            config=config,
        )

    def mint_download_url(
        self,
        project_id: str,
        job_id: UUID,
        ttl: timedelta = SIGNED_URL_TTL,
    ) -> tuple[str, datetime]:
        """Return (`signed_url`, `expires_at`).

        The URL is scoped to the full object key; the signer identity has
        no `s3:ListBucket` permission, so mutating the key path
        invalidates the signature.
        """
        key = build_object_key(self._env, project_id, job_id)
        url = self._client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self._target.bucket_name, "Key": key},
            ExpiresIn=int(ttl.total_seconds()),
            HttpMethod="GET",
        )
        expires_at = datetime.now(timezone.utc) + ttl
        return url, expires_at
