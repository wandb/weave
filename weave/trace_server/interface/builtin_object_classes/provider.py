import ipaddress
import re
import socket
from enum import Enum
from urllib.parse import urlparse

from pydantic import ConfigDict, Field, field_validator

from weave.trace_server.interface.builtin_object_classes import base_object_def

# Headers that must not appear in user-supplied extra_headers.
# https://coreweave.atlassian.net/browse/VULNMGMT-770
BLOCKED_HEADER_RE = re.compile(
    r"^(?:metadata-flavor"
    r"|x-aws-ec2-metadata-token(?:-ttl-seconds)?"
    r")$",
    re.IGNORECASE,
)

# Hostnames that must not appear in user-supplied base_url values.
# https://coreweave.atlassian.net/browse/VULNMGMT-770
BLOCKED_HOSTNAME_RE = re.compile(
    r"(?:^|\.)"
    r"(?:metadata\.google\.internal"
    r"|metadata\.goog"
    r"|metadata\.internal"
    r"|metadata\.azure\.com"
    r")\.?$",
    re.IGNORECASE,
)


INVALID_BASE_URL_MSG = "base_url is not a valid provider URL"


def _validate_provider_base_url(url: str) -> str:
    """Validate that a provider base_url is a well-formed, publicly-routable HTTP(S) URL.

    See https://coreweave.atlassian.net/browse/VULNMGMT-770
    """
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise ValueError(INVALID_BASE_URL_MSG) from exc

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(INVALID_BASE_URL_MSG)

    # urlparse silently strips a bare trailing '?', so check the raw string too.
    if "?" in url or parsed.fragment:
        raise ValueError(INVALID_BASE_URL_MSG)

    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise ValueError(INVALID_BASE_URL_MSG)

    if BLOCKED_HOSTNAME_RE.search(host):
        raise ValueError(INVALID_BASE_URL_MSG)

    # Reject non-globally-routable IP addresses.  socket.inet_aton handles
    # alternative IPv4 encodings that ipaddress.ip_address does not.
    addr = None
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        # Not a strict IP literal — try inet_aton for alternative IPv4 forms.
        try:
            packed = socket.inet_aton(host)
            addr = ipaddress.ip_address(packed)
        except OSError:
            pass  # Not any form of IP — hostname checks above are sufficient.

    if addr is not None and not addr.is_global:
        raise ValueError(INVALID_BASE_URL_MSG)

    return url


class ProviderReturnType(str, Enum):
    OPENAI = "openai"


class Provider(base_object_def.BaseObject):
    model_config = ConfigDict(validate_assignment=True)

    base_url: str
    api_key_name: str
    extra_headers: dict[str, str] = Field(default_factory=dict)
    return_type: ProviderReturnType = Field(default=ProviderReturnType.OPENAI)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        return _validate_provider_base_url(v)

    @field_validator("extra_headers")
    @classmethod
    def validate_extra_headers(cls, v: dict[str, str]) -> dict[str, str]:
        for key in v:
            if BLOCKED_HEADER_RE.match(key):
                raise ValueError("extra_headers contains a disallowed header")
        return v


class ProviderModel(base_object_def.BaseObject):
    provider: base_object_def.RefStr
    max_tokens: int
