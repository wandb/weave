import dataclasses
import datetime
import json
import math

import pydantic

from weave.trace.serialization.json_dict_keys import to_jsonable_with_json_keys


@dataclasses.dataclass
class _Holder:
    m: dict


class _Model(pydantic.BaseModel):
    m: dict
    n: int = 3


def test_keys_are_written_the_way_json_dumps_writes_them():
    val = {None: "first", "None": "second", True: "t", False: "f", 2: "i", 1.5: "x"}

    assert to_jsonable_with_json_keys(val) == json.loads(json.dumps(val))
    assert to_jsonable_with_json_keys(val) == {
        "null": "first",
        "None": "second",
        "true": "t",
        "false": "f",
        "2": "i",
        "1.5": "x",
    }


def test_nested_dicts_in_lists_and_tuples_are_converted():
    val = {"rows": [{None: 1}, ({True: 2},)]}

    assert to_jsonable_with_json_keys(val) == {"rows": [{"null": 1}, [{"true": 2}]]}


def test_keys_inside_dataclasses_and_models_are_converted():
    val = {
        "holder": _Holder({None: "first", "None": "second"}),
        "model": _Model(m={None: 1}),
    }

    assert to_jsonable_with_json_keys(val) == {
        "holder": {"m": {"null": "first", "None": "second"}},
        "model": {"m": {"null": 1}, "n": 3},
    }


def test_values_are_normalized_like_to_jsonable_python():
    val = {"at": datetime.datetime(2026, 1, 1), "s": {1}, "nan": math.nan}

    assert to_jsonable_with_json_keys(val, inf_nan_mode="null") == {
        "at": "2026-01-01T00:00:00",
        "s": [1],
        "nan": None,
    }
