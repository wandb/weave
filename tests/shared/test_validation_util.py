import pytest

from weave.shared import validation_util
from weave.trace_server import validation_util as validation_util_legacy

pytestmark = pytest.mark.trace_server


def test_trace_server_validation_util_reexports_the_same_objects() -> None:
    assert validation_util.CHValidationError is validation_util_legacy.CHValidationError
    assert validation_util.require_uuid is validation_util_legacy.require_uuid
