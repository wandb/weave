from weave.trace import constants


def test_object_name_length_is_unchanged() -> None:
    assert constants.MAX_OBJECT_NAME_LENGTH == 128
    assert constants.MAX_OP_NAME_LENGTH == 128
    assert constants.DEFAULT_CUSTOM_RUNTIME_MAX_TOKENS == 4096
