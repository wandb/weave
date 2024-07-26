"""
This test module tests the trace server interface itself. Specifically
various dictionary payload serialization and deserialization methods.

It is lightly filled out right now, but we should strive to test all
methods in the interface.
"""

import datetime
import typing

import pytest
from pydantic import BaseModel, ValidationError

from weave.trace_server import trace_server_interface as tsi


def test_call_start_req():
    general_schema_test(
        tsi.CallStartReq,
        {
            "start": {
                "project_id": "project_id",
                "op_name": "op_name",
                "started_at": datetime.datetime.now(),
                "attributes": {},
                "inputs": {},
            }
        },
        [
            PathTest(
                path=["start", "attributes"],
                valid_values=[
                    {},
                    {"something": "random"},
                    {"weave": None},
                    {"weave": {}},
                    {"weave": {"random_overlapping_key": "random"}},
                    {
                        "weave": {
                            "client_version": "string_val",
                            "source": "string_val",
                            "os_name": "string_val",
                            "os_version": "string_val",
                            "os_release": "string_val",
                            "sys_version": "string_val",
                        }
                    },
                ],
                invalid_values=[
                    None,
                    1,
                    "string",
                    # Invalid type for the Weave Key
                    {
                        "weave": {
                            "client_version": 1,
                        }
                    },
                ],
            )
        ],
    )


def test_call_end_req():
    general_schema_test(
        tsi.CallEndReq,
        {
            "end": {
                "project_id": "project_id",
                "id": "call_id",
                "ended_at": datetime.datetime.now(),
                "summary": {},
            }
        },
        [
            PathTest(
                path=["end", "summary"],
                valid_values=[
                    {},
                    {"something": "random"},
                    {"usage": None},
                    {"usage": {}},
                    {
                        "usage": {
                            "model_id": {
                                "prompt_tokens": 1,
                                "input_tokens": 1,
                                "completion_tokens": 1,
                                "output_tokens": 1,
                                "requests": 1,
                                "total_tokens": 1,
                            }
                        }
                    },
                ],
                invalid_values=[
                    None,
                    1,
                    "string",
                    # Invalid type for the usage
                    {"usage": 1},
                    {
                        "usage": {
                            1: {
                                "prompt_tokens": 1,
                                "input_tokens": 1,
                                "completion_tokens": 1,
                                "output_tokens": 1,
                                "requests": 1,
                                "total_tokens": 1,
                            }
                        }
                    },
                    {
                        "usage": {
                            1: {
                                "prompt_tokens": "a",
                            }
                        }
                    },
                ],
            )
        ],
    )


def test_call_schema():
    general_schema_test(
        tsi.CallSchema,
        {
            "id": "call_id",
            "project_id": "project_id",
            "op_name": "op_name",
            "trace_id": "trace_id",
            "started_at": datetime.datetime.now(),
            "attributes": {},
            "inputs": {},
        },
        [
            PathTest(
                path=["attributes"],
                valid_values=[
                    {},
                    {"something": "random"},
                    {"weave": None},
                    {"weave": {}},
                    {"weave": {"random_overlapping_key": "random"}},
                    {
                        "weave": {
                            "client_version": "string_val",
                            "source": "string_val",
                            "os_name": "string_val",
                            "os_version": "string_val",
                            "os_release": "string_val",
                            "sys_version": "string_val",
                        }
                    },
                ],
                invalid_values=[
                    None,
                    1,
                    "string",
                    # Invalid type for the Weave Key
                    {
                        "weave": {
                            "client_version": 1,
                        }
                    },
                ],
            ),
            PathTest(
                path=["summary"],
                valid_values=[
                    {},
                    {"something": "random"},
                    {"usage": None},
                    {"usage": {}},
                    {
                        "usage": {
                            "model_id": {
                                "prompt_tokens": 1,
                                "input_tokens": 1,
                                "completion_tokens": 1,
                                "output_tokens": 1,
                                "requests": 1,
                                "total_tokens": 1,
                            }
                        }
                    },
                ],
                invalid_values=[
                    1,
                    "string",
                    # Invalid type for the usage
                    {"usage": 1},
                    {
                        "usage": {
                            1: {
                                "prompt_tokens": 1,
                                "input_tokens": 1,
                                "completion_tokens": 1,
                                "output_tokens": 1,
                                "requests": 1,
                                "total_tokens": 1,
                            }
                        }
                    },
                    {
                        "usage": {
                            1: {
                                "prompt_tokens": "a",
                            }
                        }
                    },
                ],
            ),
        ],
    )


# Helpers Below


def with_value_at_key_path(d: dict, path: list[str], value: typing.Any) -> dict:
    res = {**d}
    if len(path) == 1:
        res[path[0]] = value
    else:
        if path[0] not in res:
            res[path[0]] = {}
        res[path[0]] = with_value_at_key_path(res[path[0]], path[1:], value)
    return res


def variations(
    d: dict, path: list[str], values: list[typing.Any]
) -> typing.Iterable[dict]:
    for value in values:
        yield with_value_at_key_path(d, path, value)


class PathTest(BaseModel):
    path: list[str]
    valid_values: list[typing.Any]
    invalid_values: list[typing.Any]


def general_schema_path_test(model: BaseModel, base: dict, path_test: PathTest):
    path = path_test.path
    valid_values = path_test.valid_values
    invalid_values = path_test.invalid_values

    for valid_variant in variations(base, path, valid_values):
        model.model_validate(valid_variant)
    for invalid_variant in variations(base, path, invalid_values):
        with pytest.raises(ValidationError):
            model.model_validate(invalid_variant)


def find_all_paths(d: dict) -> typing.Iterable[list[str]]:
    for k, v in d.items():
        if isinstance(v, dict):
            for subpath in find_all_paths(v):
                yield [k] + subpath
        else:
            yield [k]


def assert_minimal(model: BaseModel, base: dict):
    model.model_validate(base)

    for path in find_all_paths(base):
        invalid_base = with_value_at_key_path(base, path, None)
        with pytest.raises(ValidationError):
            model.model_validate(invalid_base)


def general_schema_test(model: BaseModel, base: dict, path_tests: PathTest):
    """Use this to test your pydantic model. Given a Model, a base dictionary
    and a list of PathTests, this will test the model against the base
    dictionary and the path tests.

    First, all paths in the base dictionary are tested to ensure that the
    model is minimal - meaning any null value in the base dictionary will
    cause a validation error.

    Then, for each path test, the model is tested against the base dictionary
    with the valid values and invalid values for that path.
    """
    assert_minimal(model, base)
    for path_test in path_tests:
        general_schema_path_test(model, base, path_test)
