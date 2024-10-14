import pytest

from weave.trace_server import validation
from weave.trace_server.errors import InvalidRequest


def test_validate_dict_one_key():
    with pytest.raises(InvalidRequest) as e:
        validation.validate_dict_one_key("foo", "foo", str)
    assert str(e.value) == "Expected a dictionary, got foo"

    with pytest.raises(InvalidRequest) as e:
        validation.validate_dict_one_key({}, "foo", str)
    assert str(e.value) == "Expected a dictionary with one key, got {}"

    with pytest.raises(InvalidRequest) as e:
        validation.validate_dict_one_key({"foo": "bar"}, "bar", str)
    assert str(e.value) == "Expected key bar, got foo"

    with pytest.raises(InvalidRequest) as e:
        validation.validate_dict_one_key({"foo": 12}, "foo", str)
    assert str(e.value) == "Expected value of type <class 'str'>, got <class 'int'>"

    assert validation.validate_dict_one_key({"foo": "bar"}, "foo", str) == "bar"


def test_validate_purge_req_one():
    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_one("foo")
    assert str(e.value) == "Expected a dictionary, got foo"

    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_one({"foo": "bar"})
    assert str(e.value) == "Expected key eq_, got foo"

    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_one({"eq_": "bar"})
    assert str(e.value) == "Expected value of type <class 'tuple'>, got <class 'str'>"

    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_one({"eq_": {"get_field_": 12}})
    assert str(e.value) == "Expected value of type <class 'tuple'>, got <class 'dict'>"

    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_one({"eq_": tuple([{"get_field_": "id"}])})
    assert str(e.value) == validation.MESSAGE_INVALID_PURGE

    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_one(
            {"eq_": {"get_field_": "foo"}, "literal_": "bar"}
        )
    assert (
        str(e.value)
        == "Expected a dictionary with one key, got {'eq_': {'get_field_': 'foo'}, 'literal_': 'bar'}"
    )

    validation.validate_purge_req_one(
        {"eq_": tuple([{"get_field_": "id"}, {"literal_": "bar"}])}
    )

    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_one({"in_": ()}, operator="in_")
    assert str(e.value) == validation.MESSAGE_INVALID_PURGE

    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_one(
            {"in_": tuple({"literal_": 12})}, operator="in_"
        )
    assert str(e.value) == validation.MESSAGE_INVALID_PURGE

    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_one(
            {"in_": tuple({"literal_": "bar"})}, operator="in_"
        )
    assert str(e.value) == validation.MESSAGE_INVALID_PURGE

    validation.validate_purge_req_one(
        {
            "in_": tuple(
                [
                    {"get_field_": "id"},
                    [{"literal_": "foo"}],
                ]
            )
        },
        operator="in_",
    )
    validation.validate_purge_req_one(
        {
            "in_": tuple(
                [
                    {"get_field_": "id"},
                    [{"literal_": "bar"}, {"literal_": "foo"}],
                ]
            )
        },
        operator="in_",
    )


def test_validate_purge_req_multiple():
    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_multiple("foo")
    assert str(e.value) == validation.MESSAGE_INVALID_PURGE

    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_multiple({"foo": "bar"})
    assert str(e.value) == validation.MESSAGE_INVALID_PURGE

    with pytest.raises(InvalidRequest) as e:
        validation.validate_purge_req_multiple(
            [{"eq_": {"get_field_": "id"}, "literal_": "bar"}]
        )
    assert (
        str(e.value)
        == "Expected a dictionary with one key, got {'eq_': {'get_field_': 'id'}, 'literal_': 'bar'}"
    )

    validation.validate_purge_req_multiple(
        [
            {"eq_": tuple([{"get_field_": "id"}, {"literal_": "bar"}])},
            {"eq_": tuple([{"get_field_": "id"}, {"literal_": "bar"}])},
        ]
    )
