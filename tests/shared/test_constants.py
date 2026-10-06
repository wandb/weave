import pytest

from weave.shared import constants
from weave.trace_server import constants as constants_legacy

pytestmark = pytest.mark.trace_server


def test_object_name_length_is_unchanged() -> None:
    assert constants.MAX_OBJECT_NAME_LENGTH == 128
    assert constants.MAX_OP_NAME_LENGTH == 128
    assert constants.DEFAULT_CUSTOM_RUNTIME_MAX_TOKENS == 4096


def test_trace_server_constants_reexports_the_same_values() -> None:
    assert constants.MAX_OBJECT_NAME_LENGTH is constants_legacy.MAX_OBJECT_NAME_LENGTH
    assert constants.INFERENCE_HOST is constants_legacy.INFERENCE_HOST
    assert constants.EVAL_RUN_ID_SPAN_ATTR is constants_legacy.EVAL_RUN_ID_SPAN_ATTR
