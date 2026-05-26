"""The single escaping helper for `CREATE NAMED COLLECTION` bodies.

CH does not accept `{name:T}` substitution inside `CREATE NAMED COLLECTION`,
so credential values land via Python string formatting. Every interpolated
value is validated against `CREDENTIAL_VALUE_REGEX` first; anything outside
that charset raises before any SQL is built.

Lint rule: `f"...CREATE NAMED COLLECTION..."` must not appear outside this
module.
"""

from uuid import UUID

from weave.trace_server.export.constants import (
    CREDENTIAL_VALUE_REGEX,
    NAMED_COLLECTION_PREFIX,
    URL_VALUE_REGEX,
)


class InvalidCredentialCharError(ValueError):
    """A credential value contained a char outside `CREDENTIAL_VALUE_REGEX`."""


def _validate_credential_value(name: str, value: str) -> None:
    if not value:
        raise InvalidCredentialCharError(f"empty credential value: {name}")
    if not CREDENTIAL_VALUE_REGEX.fullmatch(value):
        raise InvalidCredentialCharError(
            f"credential value for {name!r} contains characters outside the "
            f"allowed charset"
        )


def _validate_url_value(value: str) -> None:
    if not value:
        raise InvalidCredentialCharError("empty dest_url")
    if not URL_VALUE_REGEX.fullmatch(value):
        raise InvalidCredentialCharError(
            "dest_url contains characters outside the allowed URL charset"
        )


def named_collection_name(job_id: UUID) -> str:
    """Stable per-export NC identifier. UUID hex; no hyphens."""
    return f"{NAMED_COLLECTION_PREFIX}{job_id.hex}"


def build_create_named_collection_sql(
    *,
    job_id: UUID,
    access_key_id: str,
    secret_access_key: str,
    session_token: str,
    dest_url: str,
) -> str:
    """Return the CREATE NAMED COLLECTION SQL body.

    Every credential value is charset-validated; `dest_url` is too, so the
    URL parser upstream must already have rejected anything weirder than
    `[A-Za-z0-9/+=._-]`. The job_id is rendered as bare hex (UUID.hex), so
    there is no quote-escape surface in the identifier either.
    """
    _validate_credential_value("access_key_id", access_key_id)
    _validate_credential_value("secret_access_key", secret_access_key)
    _validate_credential_value("session_token", session_token)
    _validate_url_value(dest_url)

    name = named_collection_name(job_id)
    return (
        f"CREATE NAMED COLLECTION {name} AS "
        f"access_key_id = '{access_key_id}', "
        f"secret_access_key = '{secret_access_key}', "
        f"session_token = '{session_token}', "
        f"url = '{dest_url}'"
    )


def build_drop_named_collection_sql(job_id: UUID) -> str:
    return f"DROP NAMED COLLECTION IF EXISTS {named_collection_name(job_id)}"
