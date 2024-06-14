import pytest

import weave


def test_cast_basic():
    valid_cast = weave.ops.cast(1, weave.types.Int())
    assert valid_cast.type == weave.types.Int()
    assert weave.use(valid_cast) == 1

    invalid_cast = weave.ops.cast(1, weave.types.String())
    assert invalid_cast.type == weave.types.String()
    with pytest.raises(weave.errors.WeaveTypeError):
        weave.use(invalid_cast)


def test_cast_json():
    s = weave.save('{"a": 1}')
    parsed = s.json_parse().cast(weave.types.TypedDict({"a": weave.types.Int()}))
    assert parsed.type == weave.types.TypedDict({"a": weave.types.Int()})
    assert weave.use(parsed) == {"a": 1}
