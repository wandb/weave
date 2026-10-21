import pytest

from weave.utils.url_safety import is_publicly_routable_url


@pytest.mark.parametrize(
    "url",
    [
        # Shared address space (RFC 6598), including Alibaba Cloud metadata.
        "http://100.64.0.1/",
        "http://100.100.100.200/",
        # IPv6 site-local, which Python reports as global.
        "http://[fec0::1]/",
    ],
)
def test_rejects_addresses_python_does_not_classify_as_private(url: str) -> None:
    assert is_publicly_routable_url(url) is False
