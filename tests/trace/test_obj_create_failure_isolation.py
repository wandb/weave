"""Regression tests for WB-31070.

When `_save_object_basic` fails (e.g. 502 after retries), the failed
`digest_future` must not be attached to `orig_val.ref`. Otherwise the
future's exception traceback retains the serialized `json_val` via
frame locals, pinning the entire payload for the lifetime of
`orig_val`.
"""

from __future__ import annotations

import gc
import weakref
from unittest.mock import patch

import httpx
import pytest

from weave.trace.object_record import ObjectRecord
from weave.trace.weave_client import WeaveClient
from weave.trace_server_bindings.remote_http_trace_server import (
    RemoteHTTPTraceServer,
)


def _make_502(url: str = "/obj/create") -> httpx.Response:
    return httpx.Response(
        status_code=502,
        request=httpx.Request("POST", "http://example.com" + url),
        content=b"Bad Gateway",
    )


def _make_200_obj_create(digest: str = "abc123") -> httpx.Response:
    return httpx.Response(
        status_code=200,
        request=httpx.Request("POST", "http://example.com/obj/create"),
        json={"digest": digest},
    )


@pytest.fixture
def offline_client(monkeypatch):
    monkeypatch.setenv("WEAVE_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("WEAVE_RETRY_MAX_INTERVAL", "0.01")
    monkeypatch.setenv("WEAVE_ENABLE_WAL", "false")
    server = RemoteHTTPTraceServer("http://example.com")
    client = WeaveClient(
        entity="ent",
        project="proj",
        server=server,
        ensure_project_exists=False,
    )
    return client, server


def _make_record() -> ObjectRecord:
    return ObjectRecord(
        {
            "_class_name": "Blob",
            "_bases": ["Object"],
            "data": "X" * 4096,
        }
    )


@pytest.mark.disable_logging_error_check
def test_failed_obj_create_does_not_attach_ref(offline_client):
    """502 on obj/create must leave orig_val.ref unset."""
    client, server = offline_client
    obj = _make_record()

    with patch.object(server, "post", return_value=_make_502()):
        client._save_object_basic(obj, name="blob")
        client.future_executor.flush()

    assert getattr(obj, "ref", None) is None


def test_successful_obj_create_attaches_ref(offline_client):
    """200 on obj/create must attach a ref whose digest_future resolves."""
    client, server = offline_client
    obj = _make_record()

    with patch.object(server, "post", return_value=_make_200_obj_create("d1")):
        client._save_object_basic(obj, name="blob")
        client.future_executor.flush()

    ref = getattr(obj, "ref", None)
    assert ref is not None
    assert ref.digest == "d1"


@pytest.mark.disable_logging_error_check
def test_failed_obj_create_releases_payload_when_orig_dropped(offline_client):
    """After a failed save, dropping orig_val must let the payload be GC'd.

    Pre-fix: orig_val.ref pinned the failed digest_future, whose exception
    traceback retained json_val frame locals.
    """
    client, server = offline_client
    obj = _make_record()
    obj_ref = weakref.ref(obj)

    with patch.object(server, "post", return_value=_make_502()):
        client._save_object_basic(obj, name="blob")
        client.future_executor.flush()

    del obj
    gc.collect()
    assert obj_ref() is None, "orig_val should be garbage collected after drop"


def test_set_ref_unknown_type_does_not_raise_during_save(offline_client):
    """Dict path still returns a usable ref. set_ref's ValueError is
    swallowed inside the done callback.
    """
    client, server = offline_client
    payload = {"data": "X" * 1024}

    with patch.object(server, "post", return_value=_make_200_obj_create("d2")):
        ref = client._save_object_basic(payload, name="d")
        client.future_executor.flush()

    assert ref.digest == "d2"
