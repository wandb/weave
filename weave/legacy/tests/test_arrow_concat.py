import dataclasses

import pytest

import weave
from weave.legacy.weave import artifact_local, storage
from weave.legacy.weave.ops_arrow import to_arrow
from weave.legacy.weave.ops_domain import wbmedia

# This is not a valid artifact, but we need one to test. We set _read_dirname
# so that the artifact's is_saved property is True, so that everything works
# as expected.
UNSAVED_TEST_ARTIFACT = artifact_local.LocalArtifact("artifact2", "latest")
UNSAVED_TEST_ARTIFACT._read_dirname = "x"

CONCAT_TEST_CASES = [
    ([1, 2, 3], [4, 5, 6]),
    ([1, 2, 3], ["a", "b", "c"]),
    ([1, 2, 3], ["a", "b", "c", False]),
    ([1, 2, "a", {"b": 7}, {"d": 8}], [4, False, None, {"d": 8}, {"c": 9}]),
    (
        [1, None, 2, "a", {"b": 7}, {"d": 8}, {"d": None}, {"d": "j", "b": "s"}],
        [4, False, None, {"d": 8}, {"c": 9}],
    ),
    ([None, 1], ["a", None]),
    ([{}, None], [{}, None, 9]),
    ([{"a": {}}], [{"a": {}}]),
    ([1, 2, 3], [{"a": 5}]),
    ([{"a": 5}], [{"a": 9, "b": 6}]),
    ([1, 2, 3], [[4, 5], [6, 7, 8]]),
    ([[1, 2, 3]], [[4, 5], [6, 7, 8]]),
    ([{"a": [0.5]}, {"a": 8}], [{}]),
    ([{"a": [0.5]}, {"a": 8}], [{}, {"a": ["a", "b", None]}]),
    ([["a", "b"], ["c"]], [[4, 5], [6, 7, 8]]),
    ([["a", "b"], [{"x": 15}]], [[4, 5], [6, 7, 8]]),
    (
        [1, 2, 3],
        [
            wbmedia.ImageArtifactFileRef(
                UNSAVED_TEST_ARTIFACT,
                "path",
                "format",
                25,
                35,
                "sha256",
                None,
                None,
                None,
            )
        ],
    ),
    (
        [
            wbmedia.ImageArtifactFileRef(
                UNSAVED_TEST_ARTIFACT,
                "path1",
                "format1",
                25,
                35,
                "sha256-1",
                {
                    "box": [
                        {
                            "position": {
                                "maxX": 5.0,
                                "maxY": 9.0,
                                "minX": 10.0,
                                "minY": 15.0,
                            },
                            "class_id": 0,
                            "scores": {"a": 0.5},
                        }
                    ]
                },
                None,
                None,
            )
        ],
        [
            wbmedia.ImageArtifactFileRef(
                UNSAVED_TEST_ARTIFACT,
                "path2",
                "format2",
                50,
                70,
                "sha256-2",
                None,
                None,
                None,
            )
        ],
    ),
    (
        [{"a": 5, "b": None}],
        [
            {
                "a": 7,
                "b": wbmedia.ImageArtifactFileRef(
                    UNSAVED_TEST_ARTIFACT,
                    "path2",
                    "format2",
                    50,
                    70,
                    "sha256-2",
                    None,
                    None,
                    None,
                ),
            }
        ],
    ),
    (
        [{"a": 5, "b": None}],
        [
            {
                "a": 7,
                "b": wbmedia.ImageArtifactFileRef(
                    UNSAVED_TEST_ARTIFACT,
                    "path2",
                    "format2",
                    50,
                    70,
                    "sha256-2",
                    {
                        "box": [
                            {
                                "position": {
                                    "maxX": 5.0,
                                    "maxY": 9.0,
                                    "minX": 10.0,
                                    "minY": 15.0,
                                },
                                "class_id": 0,
                                "scores": {"a": 0.5},
                            }
                        ]
                    },
                    None,
                    None,
                ),
            }
        ],
    ),
    (
        [{"a": 5, "b": None}],
        [
            {
                "a": 49,
                "b": None,
            },
            {
                "a": 7,
                "b": wbmedia.ImageArtifactFileRef(
                    UNSAVED_TEST_ARTIFACT,
                    "path2",
                    "format2",
                    50,
                    70,
                    "sha256-2",
                    {
                        "box": [
                            {
                                "position": {
                                    "maxX": 5.0,
                                    "maxY": 9.0,
                                    "minX": 10.0,
                                    "minY": 15.0,
                                },
                                "class_id": 0,
                                "scores": {"a": 0.5},
                            }
                        ]
                    },
                    None,
                    None,
                ),
            },
        ],
    ),
    (
        [
            {
                "a": 7,
                "b": wbmedia.ImageArtifactFileRef(
                    UNSAVED_TEST_ARTIFACT,
                    "path2",
                    "format2",
                    50,
                    70,
                    "sha256-2",
                    {
                        "box": [
                            {
                                "position": {
                                    "maxX": 5.0,
                                    "maxY": 9.0,
                                    "minX": 10.0,
                                    "minY": 15.0,
                                },
                                "class_id": 0,
                                "scores": {"a": 0.5},
                            }
                        ]
                    },
                    None,
                    None,
                ),
            },
            {
                "a": 45,
                "b": wbmedia.ImageArtifactFileRef(
                    UNSAVED_TEST_ARTIFACT,
                    "path2",
                    "format2",
                    50,
                    70,
                    "sha256-25",
                    {"box": []},
                    None,
                    None,
                ),
            },
        ],
        [
            {"a": 10, "b": None},
            {
                "a": 11,
                "b": wbmedia.ImageArtifactFileRef(
                    UNSAVED_TEST_ARTIFACT,
                    "path2",
                    "format2",
                    67,
                    14,
                    "sha256-3",
                    {"box": []},
                    None,
                    None,
                ),
            },
        ],
    ),
]


def fix_for_compare(x1):
    if isinstance(x1, list):
        return [fix_for_compare(x) for x in x1]
    elif isinstance(x1, dict):
        return {k: fix_for_compare(v) for k, v in x1.items()}
    elif dataclasses.is_dataclass(x1):
        return x1.__class__(
            **{k: fix_for_compare(v) for k, v in dataclasses.asdict(x1).items()}
        )
    elif isinstance(x1, artifact_local.LocalArtifact):
        # Same hack as what we did to construct UNSAVED_TEST_ARTIFACT above.
        if x1._read_dirname is None:
            x1._read_dirname = "x"
        return (x1.name, x1.version)
    return x1


@pytest.mark.parametrize(
    "l1, l2",
    CONCAT_TEST_CASES,  # ids=lambda arg: str(weave.type_of(arg).object_type)
)
def test_extend(l1, l2):
    print()
    print("L1", l1)
    print("L2", l2)
    a1 = to_arrow(l1)
    a1_ref = storage.save(a1)
    a1_again = storage.get(str(a1_ref))
    assert a1.object_type == a1_again.object_type
    assert a1._arrow_data == a1_again._arrow_data
    a1 = a1_again

    a2 = to_arrow(l2)
    a2_ref = storage.save(a2)
    a2_again = storage.get(str(a2_ref))
    assert a2.object_type == a2_again.object_type
    assert a2._arrow_data == a2_again._arrow_data
    a2 = a2_again

    print("L1.object_type", a1.object_type)
    print("L2.object_type", a2.object_type)
    result = a1.concat(a2)
    expected = to_arrow(l1 + l2)
    print("EXPECTED TYPE", expected.object_type)
    print("RESULT TYPE", result.object_type)

    print("EXPECTED", expected.to_pylist_tagged())
    print("RESULT", result.to_pylist_tagged())
    # print("RESULT ARROW", result._arrow_data)
    # print("EXP ARROW", expected._arrow_data)

    # assert result.object_type == expected.object_type
    assert fix_for_compare(result.to_pylist_tagged()) == fix_for_compare(
        expected.to_pylist_tagged()
    )

    # Not working yet because of null handling
    # assert result._arrow_data == expected._arrow_data
    # assert_concat_result_equal(result.to_pylist_notags(), expected.to_pylist_notags())


CONCAT_WBTYPED_TEST_CASES = [
    # Number/Int/Floats
    # Int / Int Data, Permutations of Weave Types
    ([1, 2, 3], [4, 5, 6], weave.types.Number(), weave.types.Number()),
    ([1, 2, 3], [4, 5, 6], weave.types.Number(), weave.types.Int()),
    ([1, 2, 3], [4, 5, 6], weave.types.Int(), weave.types.Number()),
    ([1, 2, 3], [4, 5, 6], weave.types.Int(), weave.types.Int()),
    # Int / Float Data, Permutations of Weave Types
    ([1, 2, 3], [4.5, 5.5, 6.5], weave.types.Number(), weave.types.Number()),
    ([1, 2, 3], [4.5, 5.5, 6.5], weave.types.Number(), weave.types.Float()),
    ([1, 2, 3], [4.5, 5.5, 6.5], weave.types.Int(), weave.types.Number()),
    ([1, 2, 3], [4.5, 5.5, 6.5], weave.types.Int(), weave.types.Float()),
    # Float / Int Data, Permutations of Weave Types
    ([1.5, 2.5, 3.5], [4, 5, 6], weave.types.Number(), weave.types.Number()),
    ([1.5, 2.5, 3.5], [4, 5, 6], weave.types.Number(), weave.types.Int()),
    ([1.5, 2.5, 3.5], [4, 5, 6], weave.types.Float(), weave.types.Number()),
    ([1.5, 2.5, 3.5], [4, 5, 6], weave.types.Float(), weave.types.Int()),
    # Float / Float Data, Permutations of Weave Types
    ([1.5, 2.5, 3.5], [4.5, 5.5, 6.5], weave.types.Number(), weave.types.Number()),
    ([1.5, 2.5, 3.5], [4.5, 5.5, 6.5], weave.types.Number(), weave.types.Float()),
    ([1.5, 2.5, 3.5], [4.5, 5.5, 6.5], weave.types.Float(), weave.types.Number()),
    ([1.5, 2.5, 3.5], [4.5, 5.5, 6.5], weave.types.Float(), weave.types.Float()),
]


@pytest.mark.parametrize(
    "l1, l2, l1_wb_type, l2_wb_type",
    CONCAT_WBTYPED_TEST_CASES,
)
def test_concat_wbtyped(l1, l2, l1_wb_type, l2_wb_type):
    print()
    print("L1", l1)
    print("L2", l2)

    if l1_wb_type:
        l1_wb_type = weave.types.List(l1_wb_type)
    if l2_wb_type:
        l2_wb_type = weave.types.List(l2_wb_type)

    a1 = to_arrow(l1, l1_wb_type)
    a1_ref = storage.save(a1)
    a1_again = storage.get(str(a1_ref))
    assert a1.object_type == a1_again.object_type
    assert a1._arrow_data == a1_again._arrow_data
    a1 = a1_again

    a2 = to_arrow(l2, l2_wb_type)
    a2_ref = storage.save(a2)
    a2_again = storage.get(str(a2_ref))
    assert a2.object_type == a2_again.object_type


def test_image_ref():
    py = wbmedia.ImageArtifactFileRef(
        "artifact1",
        "path1",
        "format1",
        25,
        35,
        "sha256-1",
        None,
        None,
        None,
    )
    a = to_arrow([py])
    py2 = a.to_pylist_tagged()[0]
    assert py == py2


import random


def make_random_python_scalar():
    # Generate random python scalar
    rand = random.random()
    if rand < 0.2:
        return None
    elif rand < 0.4:
        return random.randint(0, 100)
    elif rand < 0.6:
        return random.random()
    elif rand < 0.8:
        return random.choice(["a", "b", "c"])
    else:
        return random.choice([True, False])


def make_random_python_list(depth=0):
    # Generate random python list
    return [
        make_random_python_val(depth=depth + 1) for _ in range(random.randint(0, 3))
    ]


def make_random_python_dict(depth=0):
    # Generate random python dict
    return {
        str(i): make_random_python_val(depth=depth + 1)
        for i in range(random.randint(0, 3))
    }


def make_random_python_val(depth=0):
    # Generate random python data with a mix of types
    rand = random.random()
    if depth > 3 or rand < 0.4:
        return make_random_python_scalar()
    elif rand < 0.7:
        return make_random_python_list(depth=depth + 1)
    else:
        return make_random_python_dict(depth=depth + 1)


random.seed(0)
random_cases = []
for i in range(100):
    l1 = [make_random_python_val() for i in range(3)]
    l2 = [make_random_python_val() for i in range(3)]
    random_cases.append((l1, l2))


@pytest.mark.parametrize("l1, l2", random_cases)
def test_random(l1, l2):
    print("L1", l1)
    print("L2", l2)
    a1 = to_arrow(l1)
    a2 = to_arrow(l2)
    result = a1.concat(a2)
    expected = to_arrow(l1 + l2)
    print("L1 OBJECT TYPE", a1.object_type)
    print("L2 OBJECT TYPE", a2.object_type)

    print("EXPECTED OBJECT TYPE", expected.object_type)
    print("RESULT OBJECT TYPE", result.object_type)
    # assert result.object_type.asdict() == expected.object_type.asdict()

    print("EXPECTED PY", expected.to_pylist_notags())
    print("RESULT PY", result.to_pylist_notags())

    assert fix_for_compare(result.to_pylist_tagged()) == fix_for_compare(
        expected.to_pylist_tagged()
    )


CONVERT_TEST_CASES = [
    ([{}, {"a": 5}], [{"a": None}, {"a": 5}]),
    ([{}, {"a": 5}, 92], [{"a": None}, {"a": 5}, 92]),
]


@pytest.mark.parametrize("l,expected", CONVERT_TEST_CASES)
def test_convert(l, expected):
    a = to_arrow(l)
    l2 = a.to_pylist_tagged()
    assert l2 == expected
