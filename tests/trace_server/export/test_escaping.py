"""The escaping helper is the only place credentials touch a string literal.

Every adversarial input the spec calls out (single-quote injection,
backslash, semicolon, ANSI control char, percent-encoded forms) must
raise; a passing test should NEVER emit a CREATE NAMED COLLECTION body
that round-trips the bad input.
"""

import uuid

import pytest

from weave.trace_server.export.escaping import (
    InvalidCredentialCharError,
    build_create_named_collection_sql,
    build_drop_named_collection_sql,
    named_collection_name,
)

VALID_AKID = "AKIAIOSFODNN7EXAMPLE"
VALID_SAK = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
VALID_STOK = "FQoGZXIvYXdzEPL//////////wEaDM=="
VALID_URL = "s3://team-bucket/prod/exports/UHJvajEyMw==/abc123/data.parquet"


def _new_job() -> uuid.UUID:
    return uuid.UUID("11111111-2222-3333-4444-555555555555")


class TestValid:
    def test_collection_name_uses_uuid_hex(self) -> None:
        nc = named_collection_name(_new_job())
        assert nc.startswith("export_")
        assert "-" not in nc
        assert len(nc) == len("export_") + 32

    def test_create_body_round_trips_valid_inputs(self) -> None:
        sql = build_create_named_collection_sql(
            job_id=_new_job(),
            access_key_id=VALID_AKID,
            secret_access_key=VALID_SAK,
            session_token=VALID_STOK,
            dest_url=VALID_URL,
        )
        assert sql.startswith("CREATE NAMED COLLECTION export_")
        assert f"access_key_id = '{VALID_AKID}'" in sql
        assert f"secret_access_key = '{VALID_SAK}'" in sql
        assert f"session_token = '{VALID_STOK}'" in sql
        assert f"url = '{VALID_URL}'" in sql

    def test_drop_body_references_same_collection(self) -> None:
        job = _new_job()
        create = build_create_named_collection_sql(
            job_id=job,
            access_key_id=VALID_AKID,
            secret_access_key=VALID_SAK,
            session_token=VALID_STOK,
            dest_url=VALID_URL,
        )
        drop = build_drop_named_collection_sql(job)
        assert named_collection_name(job) in create
        assert named_collection_name(job) in drop


class TestRejection:
    @pytest.mark.parametrize(
        ("field", "bad_value"),
        [
            ("access_key_id", "AKIA'or'1=1"),
            ("access_key_id", "AKIA\\nDROP"),
            ("access_key_id", "AKIA OR 1=1"),
            ("access_key_id", "AKIA;DROP"),
            ("access_key_id", "AKIA\x00"),
            ("access_key_id", ""),
            ("secret_access_key", "key'--"),
            ("secret_access_key", "key extra"),  # non-breaking space
            ("session_token", "tok\nnew"),
            ("session_token", "tok\rnew"),
            ("session_token", "tok\t"),
            ("session_token", "tok#"),
        ],
    )
    def test_credential_chars(self, field: str, bad_value: str) -> None:
        kwargs = {
            "access_key_id": VALID_AKID,
            "secret_access_key": VALID_SAK,
            "session_token": VALID_STOK,
        }
        kwargs[field] = bad_value
        with pytest.raises(InvalidCredentialCharError):
            build_create_named_collection_sql(
                job_id=_new_job(),
                dest_url=VALID_URL,
                **kwargs,
            )

    @pytest.mark.parametrize(
        "bad_url",
        [
            "",
            "s3://bucket/with'quote",
            "s3://bucket/with space",
            "s3://bucket/with\nnewline",
            "s3://bucket/with;semi",
            "s3://bucket/with#hash",
            "s3://bucket/with\\backslash",
        ],
    )
    def test_dest_url(self, bad_url: str) -> None:
        with pytest.raises(InvalidCredentialCharError):
            build_create_named_collection_sql(
                job_id=_new_job(),
                access_key_id=VALID_AKID,
                secret_access_key=VALID_SAK,
                session_token=VALID_STOK,
                dest_url=bad_url,
            )


def test_quote_injection_never_emits_bad_sql() -> None:
    """End-to-end: any rejected input MUST raise; never silently emit bad SQL."""
    payload = "AKIA' OR '1'='1"
    with pytest.raises(InvalidCredentialCharError):
        build_create_named_collection_sql(
            job_id=_new_job(),
            access_key_id=payload,
            secret_access_key=VALID_SAK,
            session_token=VALID_STOK,
            dest_url=VALID_URL,
        )
