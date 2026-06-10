"""Failing repro for InvalidInternalRef returning 500 instead of 4xx on call read.

A call whose output happens to hold an external `weave:///...` ref string at
rest (a programming/storage error, not malformed client input) 500s on read:
the int->ext converter raises `InvalidInternalRef`, a `ValueError` subclass the
error registry does not match by exact type, so it falls through to 500.
"""

import datetime
import uuid

import pytest

from tests.trace_server.conftest_lib.trace_server_external_adapter import (
    UserInjectingExternalTraceServer,
)
from weave.trace_server import trace_server_interface as tsi
from weave.trace_server.errors import handle_server_exception
from weave.trace_server.trace_server_converter import InvalidInternalRef

TEST_ENTITY = "shawn"


def test_invalid_internal_ref_maps_to_4xx_not_500() -> None:
    """`handle_server_exception` should map the converter's InvalidInternalRef to a
    4xx like every other ref/validation error (it subclasses ValueError -> 400),
    not 500. The registry matches by exact type, so this ValueError subclass falls
    through to 500.
    """
    result = handle_server_exception(
        InvalidInternalRef("Encountered unexpected ref format.")
    )
    assert result.status_code == 400


def test_call_read_with_persisted_external_ref_does_not_500(
    trace_server: UserInjectingExternalTraceServer,
) -> None:
    """Reading a call whose stored output is an external `weave:///...` ref must
    surface as a clean 4xx client error, not an uncaught InvalidInternalRef -> 500.

    Mirrors prod: a `weave:///...` ref persisted at rest, hit on `/call/read`,
    raises during the internal->external response conversion.
    """
    internal_server = trace_server._internal_trace_server
    ext_project_id = f"{TEST_ENTITY}/proj_invalid_ref"
    internal_project_id = trace_server._idc.ext_to_int_project_id(ext_project_id)

    call_id = str(uuid.uuid4())
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    internal_server.call_start(
        tsi.CallStartReq(
            start=tsi.StartedCallSchemaForInsert(
                project_id=internal_project_id,
                id=call_id,
                op_name="op_with_persisted_external_ref",
                trace_id=str(uuid.uuid4()),
                started_at=now,
                attributes={},
                inputs={},
            )
        )
    )
    internal_server.call_end(
        tsi.CallEndReq(
            end=tsi.EndedCallSchemaForInsert(
                project_id=internal_project_id,
                id=call_id,
                ended_at=now,
                output=f"weave:///{ext_project_id}/object/foo:v1",
                summary={},
            )
        )
    )

    try:
        res = trace_server.call_read(
            tsi.CallReadReq(project_id=ext_project_id, id=call_id)
        )
    except InvalidInternalRef as exc:
        status_code = handle_server_exception(exc).status_code
        pytest.fail(
            f"call_read raised uncaught {type(exc).__name__} mapping to "
            f"HTTP {status_code} (500); a persisted external ref should be a 4xx."
        )

    assert res.call is not None
