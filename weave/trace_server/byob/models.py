"""Pydantic models for the BYOB storage resolver.

`ResolvedStorageTarget` is the single value object passed across the trace_server
storage boundary. Credentials use a discriminated union with `SecretStr` so raw
values cannot leak through repr, logs, or exceptions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, SecretStr


class StorageResolveStatus(str, Enum):
    BYOB = "byob"
    DEFAULT = "default"


class StorageResolvePurpose(str, Enum):
    WRITE = "write"
    READ = "read"
    INTERNAL_JOB = "internal_job"


class StorageProvider(str, Enum):
    S3 = "s3"
    GCS = "gs"
    AZURE = "az"


class S3TemporaryCredentials(BaseModel):
    credential_type: Literal["s3_temporary"] = "s3_temporary"
    access_key_id: str
    secret_access_key: SecretStr
    session_token: SecretStr


class GCSAccessTokenCredentials(BaseModel):
    credential_type: Literal["gcs_access_token"] = "gcs_access_token"
    access_token: SecretStr


class AzureSasCredentials(BaseModel):
    credential_type: Literal["azure_sas"] = "azure_sas"
    sas_token: SecretStr


class AmbientCredentials(BaseModel):
    credential_type: Literal["ambient"] = "ambient"


StorageCredentials = Annotated[
    S3TemporaryCredentials | GCSAccessTokenCredentials | AzureSasCredentials | AmbientCredentials,
    Field(discriminator="credential_type"),
]


class ResolvedStorageTarget(BaseModel):
    status: StorageResolveStatus
    provider: StorageProvider
    bucket_uri: str
    bucket_name: str
    region: str | None
    credentials: StorageCredentials
    credentials_expires_at: datetime | None
    key_prefix: str
    source_project_id: str


class StorageResolutionError(Exception):
    """Fail-closed signal; never silently fall back to default."""
