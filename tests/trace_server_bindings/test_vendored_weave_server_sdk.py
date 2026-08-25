"""Tests for the vendored copy of the generated trace server client.

The copy is regenerated in wandb/core and re-vendored by
scripts/vendor_weave_server_sdk.py, which rewrites the two places the generated
package names itself; see weave/vendor/README.md. These tests verify that both
rewrites still name the vendored path.
"""

from __future__ import annotations

import pickle

import httpx

from weave.vendor import weave_server_sdk
from weave.vendor.weave_server_sdk._utils import _resources_proxy


def test_lazy_resources_proxy_imports_the_vendored_module():
    """Test that the proxy the package installs resolves the vendored module."""
    assert (
        _resources_proxy.resources.__name__ == "weave.vendor.weave_server_sdk.resources"
    )


def test_reexported_httpx_class_stays_picklable():
    """Test that a rewritten __module__ still names a module that imports."""
    assert weave_server_sdk.Timeout is httpx.Timeout
    assert httpx.Timeout.__module__ == "weave.vendor.weave_server_sdk"
    assert pickle.loads(pickle.dumps(httpx.Timeout(5.0))) == httpx.Timeout(5.0)
